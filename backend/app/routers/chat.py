"""
app/routers/chat.py — 对话 API

REST:
GET /api/chat/conversations/{review_id}           获取或创建会话
GET /api/chat/conversations/{conv_id}/messages    消息历史
POST /api/chat/conversations/{conv_id}/messages   非流式提问（降级用）

WebSocket:
/ws/chat/{conv_id}?token=xxx    流式对话
  客户端发: {"type": "question", "content": "..."}
  服务端回: {"type": "delta", "content": "..."} × N
            {"type": "done", "answer": "完整回复"}
            {"type": "error", "message": "..."}
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db, SessionLocal
from app.core.dependencies import get_current_user, TokenPayload
from app.core.rate_limit import chat_limiter
from app.core.security import decode_access_token, TokenPayload as TP
from app.core.exceptions import NotFoundError, PermissionError, AppError
from app.models.conversation import Conversation
from app.services import chat_service
from app.schemas.conversation import (
    ConversationOut, MessageOut, QuestionIn, QuestionOut,
)

settings = get_settings()

router = APIRouter()       # REST：挂到 /api/chat
ws_router = APIRouter()    # WebSocket：挂到根 /ws


@router.get("/conversations/{review_id}", response_model=ConversationOut)
async def get_conversation(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    conv = await chat_service.get_or_create_conversation(
        db, review_id, current.user_id, current.role.value == "admin"
    )
    return ConversationOut(id=conv.id, review_id=conv.review_id)


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conv_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    conv = await _get_conv_checked(db, conv_id, current)
    history = await chat_service.get_history(db, conv.id)
    return [MessageOut(id=m.id, role=m.role.value, content=m.content, created_at=m.created_at) for m in history]


async def _get_conv_checked(db: AsyncSession, conv_id: int, current: TokenPayload) -> Conversation:
    conv = (await db.execute(
        select(Conversation).where(Conversation.id == conv_id)
    )).scalar_one_or_none()
    if not conv:
        raise NotFoundError("会话不存在")
    if current.role.value != "admin" and conv.user_id != current.user_id:
        raise PermissionError("无权访问此会话")
    return conv


@router.post("/conversations/{conv_id}/messages", response_model=QuestionOut)
async def post_message(
    conv_id: int,
    body: QuestionIn,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """非流式提问（WebSocket 不可用时的降级路径）"""
    await _get_conv_checked(db, conv_id, current)

    allowed, wait = chat_limiter.allow(
        f"chat:{current.user_id}", settings.RATE_LIMIT_CHAT_PER_MINUTE
    )
    if not allowed:
        raise AppError(f"提问过于频繁，请 {wait} 秒后再试", code=429)

    citations: list[dict] = []

    async def _collect() -> str:
        chunks: list[str] = []
        async for delta in chat_service.stream_chat_answer(db, conv_id, body.content, citations):
            chunks.append(delta)
        return "".join(chunks)

    try:
        answer = await asyncio.wait_for(_collect(), timeout=settings.CHAT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise AppError(
            f"回复超时（超过 {settings.CHAT_TIMEOUT_SECONDS} 秒），请重试",
            code=504,
        )
    await chat_service.persist_messages(db, conv_id, body.content, answer)
    return QuestionOut(answer=answer, citations=citations)


# —————————— WebSocket ——————————
@ws_router.websocket("/ws/chat/{conv_id}")
async def ws_chat(websocket: WebSocket, conv_id: int, token: str = ""):
    """流式对话；鉴权走 query 参数 ?token=<jwt>"""
    # 1) 鉴权
    if not token:
        await websocket.close(code=4401, reason="缺少 token")
        return
    try:
        payload = decode_access_token(token)
        current = TP(payload)
    except Exception:
        await websocket.close(code=4401, reason="token 无效或已过期")
        return

    await websocket.accept()

    # 2) 每条 WebSocket 连接独立 DB 会话（不走 Depends）
    async with SessionLocal() as db:
        try:
            await _get_conv_checked(db, conv_id, current)
        except AppError as e:
            await websocket.send_json({"type": "error", "message": e.message})
            await websocket.close(code=4403)
            return

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                    question = (data.get("content") or "").strip()
                except json.JSONDecodeError:
                    question = raw.strip()
                if not question:
                    await websocket.send_json({"type": "error", "message": "问题不能为空"})
                    continue

                # 流式推增量（PRD 4.4：30 秒超时，超时保留已生成部分）
                allowed, wait = chat_limiter.allow(
                    f"chat:{current.user_id}", settings.RATE_LIMIT_CHAT_PER_MINUTE
                )
                if not allowed:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"提问过于频繁，请 {wait} 秒后再试",
                    })
                    continue

                chunks: list[str] = []
                citations: list[dict] = []
                timed_out = False
                try:
                    async with asyncio.timeout(settings.CHAT_TIMEOUT_SECONDS):
                        async for delta in chat_service.stream_chat_answer(
                            db, conv_id, question, citations
                        ):
                            chunks.append(delta)
                            await websocket.send_json({"type": "delta", "content": delta})
                except TimeoutError:
                    timed_out = True

                answer = "".join(chunks)
                if answer:
                    await chat_service.persist_messages(db, conv_id, question, answer)

                if timed_out:
                    await websocket.send_json({
                        "type": "error",
                        "message": (
                            f"回复超时（超过 {settings.CHAT_TIMEOUT_SECONDS} 秒），"
                            f"已返回已生成内容，请重试"
                        ),
                    })
                else:
                    await websocket.send_json({
                        "type": "done",
                        "answer": answer,
                        "citations": citations,
                    })

        except WebSocketDisconnect:
            return
        except Exception as e:
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass

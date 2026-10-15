"""
app/routers/assistant.py — 通用法律智能问答 API

REST（挂到 /api/assistant）：
POST   /sessions                     新建会话
GET    /sessions                     我的会话列表
GET    /sessions/{id}/messages       历史消息
POST   /sessions/{id}/messages       非流式提问（WebSocket 不可用时的降级路径）
DELETE /sessions/{id}                删除会话

WebSocket（挂到根 /ws）：
/ws/assistant/{session_id}?token=<jwt>
  客户端发: {"type": "question", "content": "..."}  或裸文本
  服务端回: {"type": "delta", "content": "..."} × N
            {"type": "done", "answer": "完整回复"}
            {"type": "error", "message": "..."}
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, SessionLocal
from app.core.dependencies import get_current_user, TokenPayload
from app.core.security import decode_access_token, TokenPayload as TP
from app.core.exceptions import AppError
from app.services import assistant_service
from app.schemas.assistant import (
    SessionCreateIn, SessionOut, MessageOut, QuestionIn, QuestionOut,
)

router = APIRouter()       # REST
ws_router = APIRouter()    # WebSocket


# —————————— 会话 ——————————
@router.post("/sessions", response_model=SessionOut)
async def create_session(
    body: SessionCreateIn | None = None,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    sess = await assistant_service.create_session(
        db, current.user_id, body.title if body else None
    )
    return SessionOut(
        id=sess.id, title=sess.title, message_count=0,
        created_at=sess.created_at, last_active_at=sess.last_active_at,
    )


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    return await assistant_service.list_sessions(db, current.user_id)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    await assistant_service.get_session_checked(
        db, session_id, current.user_id, current.role.value == "admin"
    )
    history = await assistant_service.get_history(db, session_id)
    return [
        MessageOut(id=m.id, role=m.role.value, content=m.content, created_at=m.created_at)
        for m in history
    ]


@router.post("/sessions/{session_id}/messages", response_model=QuestionOut)
async def post_message(
    session_id: int,
    body: QuestionIn,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """非流式提问（降级路径）"""
    await assistant_service.get_session_checked(
        db, session_id, current.user_id, current.role.value == "admin"
    )
    chunks: list[str] = []
    async for delta in assistant_service.stream_answer(db, session_id, body.content):
        chunks.append(delta)
    answer = "".join(chunks)
    await assistant_service.persist_messages(db, session_id, body.content, answer)
    return QuestionOut(answer=answer)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    await assistant_service.delete_session(
        db, session_id, current.user_id, current.role.value == "admin"
    )
    return {"code": 0, "data": {"deleted": session_id}, "message": ""}


# —————————— WebSocket 流式 ——————————
@ws_router.websocket("/ws/assistant/{session_id}")
async def ws_assistant(websocket: WebSocket, session_id: int, token: str = ""):
    """流式问答；鉴权走 query 参数 ?token=<jwt>"""
    if not token:
        await websocket.close(code=4401, reason="缺少 token")
        return
    try:
        current = TP(decode_access_token(token))
    except Exception:
        await websocket.close(code=4401, reason="token 无效或已过期")
        return

    await websocket.accept()

    # 每条连接独立 DB 会话（不走 Depends）
    async with SessionLocal() as db:
        try:
            await assistant_service.get_session_checked(
                db, session_id, current.user_id, current.role.value == "admin"
            )
        except AppError as e:
            await websocket.send_json({"type": "error", "message": e.message})
            await websocket.close(code=4403)
            return

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    question = (json.loads(raw).get("content") or "").strip()
                except json.JSONDecodeError:
                    question = raw.strip()
                if not question:
                    await websocket.send_json({"type": "error", "message": "问题不能为空"})
                    continue

                chunks: list[str] = []
                async for delta in assistant_service.stream_answer(db, session_id, question):
                    chunks.append(delta)
                    await websocket.send_json({"type": "delta", "content": delta})

                answer = "".join(chunks)
                await assistant_service.persist_messages(db, session_id, question, answer)
                await websocket.send_json({"type": "done", "answer": answer})

        except WebSocketDisconnect:
            return
        except Exception as e:
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass

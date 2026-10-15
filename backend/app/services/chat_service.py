"""
app/services/chat_service.py — 对话追问业务逻辑

流程：用户问题 → RAG 检索证据 → 组装 Prompt（审查报告摘要 + 证据 + 最近历史 + 问题）
→ LLM 流式输出 → 双方消息落库
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionError
from app.models.conversation import Conversation, Message, ConversationRole
from app.models.review import Review, RiskItem
from app.models.contract import Contract
from app.rag.retriever import retrieve_for_chat
from app.llm.factory import get_llm

# 送给 LLM 的最近历史条数（控制 token）
HISTORY_WINDOW = 10


async def get_or_create_conversation(
    db: AsyncSession, review_id: int, user_id: int, is_admin: bool = False
) -> Conversation:
    """一份审查报告对应一个会话；校验报告归属"""
    review = (await db.execute(select(Review).where(Review.id == review_id))).scalar_one_or_none()
    if not review:
        raise NotFoundError("审查报告不存在")
    contract = (await db.execute(select(Contract).where(Contract.id == review.contract_id))).scalar_one()
    if not is_admin and contract.uploader_id != user_id:
        raise PermissionError("无权访问此报告的对话")

    conv = (await db.execute(
        select(Conversation).where(Conversation.review_id == review_id)
    )).scalar_one_or_none()
    if not conv:
        conv = Conversation(review_id=review_id, user_id=contract.uploader_id)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
    return conv


async def get_history(db: AsyncSession, conversation_id: int, limit: int = 200) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


def _build_summary(review: Review, items: list[RiskItem]) -> str:
    """审查报告摘要（对话的背景上下文）"""
    lines = [f"合同审查结论：整体风险 {review.overall_risk.value if review.overall_risk else '未知'}。风险项："]
    for it in items:
        tag = "正面发现" if it.is_positive else f"{it.risk_level.value}风险"
        lines.append(f"- [{tag}][{it.category_name}] {it.issue or it.contract_snippet[:50]}")
    return "\n".join(lines)


def _build_evidence_block(evidences: list[dict]) -> str:
    if not evidences:
        return "（知识库无相关检索结果，请基于审查报告与通用法律知识回答）"
    lines = []
    for ev in evidences:
        src = ev["metadata"].get("source_filename", "知识库")
        lines.append(f"- [来源:{src} | 相似度:{ev['similarity']}] {ev['text'][:300]}")
    return "\n".join(lines)


CHAT_SYSTEM_TEMPLATE = """你是合同审查智能助手。用户正在查看一份已完成审查的合同报告，会围绕报告内容追问。

## 审查报告摘要
{summary}

## 知识库检索证据
{evidence}

回答要求：
1. 紧扣审查报告内容与检索证据回答；证据不足以支撑时明确说明
2. 涉及具体风险时引用合同原文片段
3. 回答专业但易懂，篇幅适中（200-400字）
4. 你不是律师，涉及重大决策时提醒用户咨询专业法律人士"""


async def stream_chat_answer(
    db: AsyncSession,
    conversation_id: int,
    question: str,
):
    """
    完整对话流程（async generator，逐段 yield 文本增量）
    调用方负责在结束后调用 persist_messages 落库
    """
    # 会话与报告上下文
    conv = (await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )).scalar_one_or_none()
    if not conv:
        raise NotFoundError("会话不存在")

    review = (await db.execute(select(Review).where(Review.id == conv.review_id))).scalar_one()
    items = list((await db.execute(
        select(RiskItem).where(RiskItem.review_id == review.id)
    )).scalars().all())
    summary = _build_summary(review, items)

    # RAG 检索
    evidences = await retrieve_for_chat(question)
    evidence_block = _build_evidence_block(evidences)

    # 历史窗口
    history = await get_history(db, conversation_id, limit=HISTORY_WINDOW)
    history_msgs = [
        {"role": m.role.value, "content": m.content} for m in history
    ]

    messages = (
        [{"role": "system", "content": CHAT_SYSTEM_TEMPLATE.format(summary=summary, evidence=evidence_block)}]
        + history_msgs
        + [{"role": "user", "content": question}]
    )

    llm = get_llm()
    async for delta in llm.stream_chat(messages, temperature=0.4):
        yield delta


async def persist_messages(
    db: AsyncSession, conversation_id: int, question: str, answer: str
) -> None:
    db.add(Message(conversation_id=conversation_id, role=ConversationRole.USER, content=question))
    db.add(Message(conversation_id=conversation_id, role=ConversationRole.ASSISTANT, content=answer))
    await db.commit()

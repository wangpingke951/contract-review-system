"""
app/services/assistant_service.py — 通用法律智能问答

与 chat_service（合同报告追问）的区别：
- 不绑定任何合同/审查报告，会话独立存在
- 面向日常高频场景：劳动、租房、消费、借贷、买卖、婚姻家事、交通事故、物业等
- 复用同一套 RAG 检索（retrieve_for_chat）与大模型抽象层
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionError
from app.models.assistant import AssistantSession, AssistantMessage, AssistantRole
from app.rag.retriever import retrieve_for_chat
from app.llm.factory import get_llm

# 送给 LLM 的最近历史条数（控制 token）
HISTORY_WINDOW = 12
# 会话标题取首轮提问的前 N 字
TITLE_MAX = 24


# —————————— 会话管理 ——————————
async def create_session(
    db: AsyncSession, user_id: int, title: Optional[str] = None
) -> AssistantSession:
    sess = AssistantSession(user_id=user_id, title=(title or "新的法律咨询")[:TITLE_MAX])
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


async def list_sessions(db: AsyncSession, user_id: int) -> list[dict]:
    """当前用户的会话列表（按最近活跃排序，带消息数）"""
    cnt = (
        select(AssistantMessage.session_id, func.count(AssistantMessage.id).label("n"))
        .group_by(AssistantMessage.session_id)
        .subquery()
    )
    rows = (await db.execute(
        select(AssistantSession, func.coalesce(cnt.c.n, 0))
        .outerjoin(cnt, cnt.c.session_id == AssistantSession.id)
        .where(AssistantSession.user_id == user_id)
        .order_by(AssistantSession.last_active_at.desc())
        .limit(100)
    )).all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "message_count": int(n),
            "created_at": s.created_at,
            "last_active_at": s.last_active_at,
        }
        for s, n in rows
    ]


async def get_session_checked(
    db: AsyncSession, session_id: int, user_id: int, is_admin: bool = False
) -> AssistantSession:
    sess = (await db.execute(
        select(AssistantSession).where(AssistantSession.id == session_id)
    )).scalar_one_or_none()
    if not sess:
        raise NotFoundError("会话不存在")
    if not is_admin and sess.user_id != user_id:
        raise PermissionError("无权访问此会话")
    return sess


async def delete_session(
    db: AsyncSession, session_id: int, user_id: int, is_admin: bool = False
) -> None:
    sess = await get_session_checked(db, session_id, user_id, is_admin)
    await db.delete(sess)   # messages 由 ON DELETE CASCADE 连带清理
    await db.commit()


async def get_history(
    db: AsyncSession, session_id: int, limit: int = 200
) -> list[AssistantMessage]:
    result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session_id)
        .order_by(AssistantMessage.id.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


# —————————— 问答链路 ——————————
def _build_evidence_block(evidences: list[dict]) -> str:
    if not evidences:
        return "（知识库暂无相关检索结果，请基于你掌握的法律知识回答，并说明该结论未经知识库印证）"
    lines = []
    for ev in evidences:
        src = ev["metadata"].get("source_filename", "知识库")
        lines.append(f"- [来源:{src} | 相似度:{ev['similarity']}] {ev['text'][:400]}")
    return "\n".join(lines)


ASSISTANT_SYSTEM_PROMPT = """你是「法律智能助手」，为普通用户解答日常生活和工作中常见的法律问题。

覆盖场景：劳动合同（试用期、加班、离职、经济补偿、竞业限制）、房屋租赁（押金、维修、转租、提前退租）、
消费维权（退换货、预付卡、霸王条款）、民间借贷（利息、借条、诉讼时效）、买卖与网购、婚姻家事、
交通事故、物业纠纷等。

## 知识库检索证据
{evidence}

回答要求：
1. 先给结论，再讲依据，最后给可执行建议
2. 优先引用检索证据中的法条与要点，并注明来源；证据不足时明确说明"以下基于一般法律常识"
3. 建议要具体：该做什么、保留什么证据、有没有时限（如诉讼时效、仲裁申请期限）
4. 涉及金额或时间计算时写出计算过程
5. 用小标题或要点组织，避免长篇大论；篇幅控制在 400 字以内，除非用户要求详细展开
6. 结尾用一句话提醒：具体情形可能有差异，重大权益问题建议咨询执业律师
7. 如果用户问的是与法律无关的内容，礼貌说明你主要负责法律相关问题，并引导回法律话题"""


async def stream_answer(
    db: AsyncSession,
    session_id: int,
    question: str,
):
    """流式问答（async generator，逐段 yield 文本增量）；调用方负责落库"""
    # 会话存在性（权限在路由层已校验）
    sess = (await db.execute(
        select(AssistantSession).where(AssistantSession.id == session_id)
    )).scalar_one_or_none()
    if not sess:
        raise NotFoundError("会话不存在")

    # RAG 检索（与合同追问共用检索层，对话场景阈值较宽松）
    evidences = await retrieve_for_chat(question, k=6)
    evidence_block = _build_evidence_block(evidences)

    # 历史窗口
    history = await get_history(db, session_id, limit=HISTORY_WINDOW)
    history_msgs = [{"role": m.role.value, "content": m.content} for m in history]

    messages = (
        [{"role": "system", "content": ASSISTANT_SYSTEM_PROMPT.format(evidence=evidence_block)}]
        + history_msgs
        + [{"role": "user", "content": question}]
    )

    llm = get_llm()
    async for delta in llm.stream_chat(messages, temperature=0.5):
        yield delta


async def persist_messages(
    db: AsyncSession, session_id: int, question: str, answer: str
) -> None:
    """落库双方消息；首轮提问用问题内容生成会话标题"""
    # 注意：必须在 add 之前统计，否则 select 的 autoflush 会把新消息一起算进去
    existing = (await db.execute(
        select(func.count(AssistantMessage.id)).where(AssistantMessage.session_id == session_id)
    )).scalar() or 0

    sess = (await db.execute(
        select(AssistantSession).where(AssistantSession.id == session_id)
    )).scalar_one_or_none()

    db.add(AssistantMessage(session_id=session_id, role=AssistantRole.USER, content=question))
    db.add(AssistantMessage(session_id=session_id, role=AssistantRole.ASSISTANT, content=answer))

    if sess and existing == 0 and sess.title == "新的法律咨询":
        sess.title = question.strip().replace("\n", " ")[:TITLE_MAX] or "新的法律咨询"
    await db.commit()

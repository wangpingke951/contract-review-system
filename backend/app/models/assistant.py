"""AssistantSession + AssistantMessage ORM — 通用法律智能问答

与 conversations/messages 的区别：
- conversations 强制绑定 review_id（一份审查报告对应一个会话）
- 本模块会话独立存在，面向日常法律咨询（劳动/租房/消费/借贷…），不依赖任何合同

刻意新建表而不改造 conversations：项目用 Base.metadata.create_all 建表，
对已存在的表不会修改列定义，把 review_id 改成可空在已有库上不会生效。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AssistantRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class AssistantSession(Base):
    """一次独立的智能问答会话"""
    __tablename__ = "assistant_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 会话标题：首轮提问的前若干字，便于会话列表识别
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="新的法律咨询")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(), nullable=False,
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=False,
    )


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("assistant_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role: Mapped[AssistantRole] = mapped_column(
        SQLEnum(AssistantRole, name="assistant_role"), nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(), nullable=False,
    )

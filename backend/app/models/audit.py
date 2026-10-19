"""
app/models/audit.py — 操作审计日志（PRD 5.3，P1）

记录的关键动作：
- 合同：上传、发起审查、重新审查、删除
- 知识库：上传、替换、删除
- 认证：登录
管理员可在后台按动作类型筛选查看。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# 动作枚举值（数据库里存字符串，新增动作无需改表结构）
ACTION_CONTRACT_UPLOAD = "contract.upload"
ACTION_CONTRACT_DELETE = "contract.delete"
ACTION_REVIEW_CREATE = "review.create"
ACTION_REVIEW_RETRY = "review.retry"
ACTION_REVIEW_ITEM_HANDLE = "review.item_handle"
ACTION_REVIEW_FINALIZE = "review.finalize"
ACTION_REVIEW_UNFINALIZE = "review.unfinalize"
ACTION_KNOWLEDGE_UPLOAD = "knowledge.upload"
ACTION_KNOWLEDGE_REPLACE = "knowledge.replace"
ACTION_KNOWLEDGE_DELETE = "knowledge.delete"
ACTION_AUTH_LOGIN = "auth.login"

ACTION_LABELS = {
    ACTION_CONTRACT_UPLOAD: "上传合同",
    ACTION_CONTRACT_DELETE: "删除合同",
    ACTION_REVIEW_CREATE: "发起审查",
    ACTION_REVIEW_RETRY: "重新审查",
    ACTION_REVIEW_ITEM_HANDLE: "处置风险项",
    ACTION_REVIEW_FINALIZE: "报告定稿",
    ACTION_REVIEW_UNFINALIZE: "取消定稿",
    ACTION_KNOWLEDGE_UPLOAD: "上传知识文档",
    ACTION_KNOWLEDGE_REPLACE: "替换知识文档",
    ACTION_KNOWLEDGE_DELETE: "删除知识文档",
    ACTION_AUTH_LOGIN: "登录",
}


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 操作人（用户被删后置空，但保留姓名快照便于追溯）
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    actor_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(), nullable=False, index=True,
    )

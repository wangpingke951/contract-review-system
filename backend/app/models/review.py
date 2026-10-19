"""Review + RiskItem ORM — 审查报告 + 风险项"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from sqlalchemy import DateTime, String, Integer, Column, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OverallRisk(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewStatus(str, Enum):
    RUNNING = "running"   # 审查进行中（异步执行）
    DONE = "done"
    FAILED = "failed"


class RiskLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskItemStatus(str, Enum):
    """风险项人工处置状态（PRD P1：确认 / 忽略 / 标记待改）"""
    PENDING = "pending"      # 待处理（默认）
    CONFIRMED = "confirmed"  # 已确认
    IGNORED = "ignored"      # 已忽略
    TODO = "todo"            # 标记待改


class Review(Base):
    """一份合同对应一份审查报告"""
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contracts.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    overall_risk: Mapped[OverallRisk | None] = mapped_column(
        SQLEnum(OverallRisk, name="overall_risk"), nullable=True,
    )
    status: Mapped[ReviewStatus] = mapped_column(
        SQLEnum(ReviewStatus, name="review_status"),
        nullable=False, default=ReviewStatus.DONE,
    )
    # 审查失败原因（异步执行时前端轮询展示）
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ——— 审查模板（不同合同类型用不同审查维度）———
    template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    template_name: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 快照

    # ——— 报告定稿（定稿后锁定，不可再修改风险项）———
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    finalized_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False,
    )


class RiskItem(Base):
    """审查报告中的单条风险提示"""
    __tablename__ = "risk_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SQLEnum(RiskLevel, name="risk_level"), nullable=False,
    )
    # 风险类别（快照存储：风险类别可能被管理员增删，历史报告保留原始值）
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("risk_categories.id", ondelete="SET NULL"), nullable=True,
    )
    category_name: Mapped[str] = mapped_column(String(128), nullable=False)  # 快照

    # 合同原文片段
    contract_snippet: Mapped[str] = mapped_column(Text, nullable=False)
    # 风险说明
    issue: Mapped[str] = mapped_column(Text, nullable=True)
    # 修改建议
    suggestion: Mapped[str] = mapped_column(Text, nullable=True)
    # 是正向发现还是风险
    is_positive: Mapped[bool] = mapped_column(default=False, nullable=False)
    # 触发依据的知识条目 ID 列表（JSON 字符串，Chromadb 的 document_id）
    source_knowledge_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 原文在合同全文中的字符位置（用于前端高亮定位）
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 人工处置状态：待处理 / 已确认 / 已忽略 / 待修改
    status: Mapped[RiskItemStatus] = mapped_column(
        SQLEnum(RiskItemStatus, name="risk_item_status"),
        nullable=False,
        default=RiskItemStatus.PENDING,
    )
    # 处置时间（便于审计）
    handled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

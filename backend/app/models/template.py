"""
app/models/template.py — 审查模板

不同合同类型关注点不同（采购合同看付款/交付，劳动合同看竞业/社保），
模板把「审查维度清单」变成管理员可配置的数据，而不是写死在代码里。

dimensions 存 JSON 字符串：
[{"name": "付款条款", "prompt": "付款方式、账期、验收与质保金是否合理", "weight": 1}]
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReviewTemplate(Base):
    __tablename__ = "review_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 审查维度 JSON（见模块 docstring）
    dimensions: Mapped[str] = mapped_column(Text, nullable=False)
    # 默认模板：发起审查未指定模板时使用
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(), nullable=False,
    )

"""
app/models/system.py — 系统运行配置（管理员可在线修改）

目前存放模型相关配置：LLM 提供商 / Key / 模型名 / BaseURL，以及视觉模型。
数据库里有值时优先于 .env，改完立即生效（见 config_service.reload）。
单行表，固定 id=1。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # ——— 主模型（审查 / 追问 / 法律问答）———
    llm_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    llm_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    llm_base_url: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # ——— 视觉模型（图片合同识别）———
    vision_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vision_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    vision_base_url: Mapped[str | None] = mapped_column(String(256), nullable=True)

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

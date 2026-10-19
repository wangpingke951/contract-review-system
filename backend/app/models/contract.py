"""Contract ORM — 用户上传的合同文档"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from sqlalchemy import DateTime, String, Integer, Column, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContractStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    PARSING_FAILED = "parsing_failed"
    REVIEWING = "reviewing"
    REVIEW_DONE = "review_done"
    REVIEW_FAILED = "review_failed"


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)   # pdf / docx / png / jpg
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[ContractStatus] = mapped_column(
        SQLEnum(ContractStatus, name="contract_status"),
        nullable=False,
        default=ContractStatus.UPLOADED,
        index=True,
    )
    # 结构化后的全文（解析完成后写入）
    parsed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 结构化章节 JSON（解析完成后写入）
    parsed_sections: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 解析失败原因（面向用户的可操作提示，成功时为 NULL）
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    uploader_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False,
    )

    # ——— 合同版本（同一份合同反复修改后重新上传）———
    # version 从 1 开始；root_contract_id 指向同族首版，parent_contract_id 指向上一版
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    root_contract_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    parent_contract_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

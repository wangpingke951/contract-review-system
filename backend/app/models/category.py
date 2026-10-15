"""RiskCategory + KnowledgeDoc ORM — 风险类别 + 知识文档"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from sqlalchemy import DateTime, String, Integer, Column, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KnowledgeCategory(str, Enum):
    TEMPLATE = "template"   # 合同模板
    GUIDE = "guide"         # 审查指引 / 法规条文
    CASE = "case"           # 历史判例
    LAW = "law"             # 法律法规


class KnowledgeStatus(str, Enum):
    CHUNKING = "chunking"    # 切块中
    ENABLED = "enabled"      # 已启用（切块完成，可被检索）
    FAILED = "failed"        # 切块失败


class RiskCategory(Base):
    """管理员可增删的风险类别"""
    __tablename__ = "risk_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False,
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )


class KnowledgeDoc(Base):
    """管理员上传的知识文档"""
    __tablename__ = "knowledge_docs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[KnowledgeCategory] = mapped_column(
        SQLEnum(KnowledgeCategory, name="knowledge_category"), nullable=False,
    )
    status: Mapped[KnowledgeStatus] = mapped_column(
        SQLEnum(KnowledgeStatus, name="knowledge_status"),
        nullable=False, default=KnowledgeStatus.CHUNKING,
    )
    # 切块完成后更新（ChromaDB upsert 的 chunk 数量）
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # ChromaDB 里的 collection 内的 metadata 主键
    chroma_source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    uploader_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False,
    )

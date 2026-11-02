"""app/schemas/admin.py — 管理后台 Pydantic 模型"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class KnowledgeDocOut(BaseModel):
    id: int
    filename: str
    category: str
    status: str
    chunk_count: int
    created_at: datetime
    # 异步摄入进度（0-100）；status=enabled 时为 100
    progress: int = 0
    processed_chunks: int = 0
    total_chunks: int = 0
    error_message: Optional[str] = None


class KnowledgeBatchUploadResponse(BaseModel):
    """批量上传回执：逐个文件给出结果，失败的不会中断其它文件"""
    uploaded: List[KnowledgeDocOut] = Field(default_factory=list)
    rejected: List[dict] = Field(default_factory=list)


class KnowledgeProgressOut(BaseModel):
    id: int
    status: str
    progress: int
    processed_chunks: int
    total_chunks: int
    chunk_count: int
    error_message: Optional[str] = None


class KnowledgeVersionOut(BaseModel):
    id: int
    filename: str
    category: str
    chunk_count: int
    replaced_at: datetime


class CategoryOut(BaseModel):
    id: int
    name: str
    created_at: datetime


class CategoryCreate(BaseModel):
    name: str


class AuditLogOut(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_name: str
    action: str
    target_type: str = ""
    target_id: Optional[int] = None
    detail: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: List[AuditLogOut]
    total: int

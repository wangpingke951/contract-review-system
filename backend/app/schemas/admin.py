"""app/schemas/admin.py — 管理后台 Pydantic 模型"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class KnowledgeDocOut(BaseModel):
    id: int
    filename: str
    category: str
    status: str
    chunk_count: int
    created_at: datetime


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

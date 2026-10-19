"""app/schemas/template.py — 审查模板 Pydantic 模型"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class DimensionIn(BaseModel):
    name: str
    prompt: str
    weight: int = 1


class TemplateOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    dimensions: List[dict] = []
    is_default: bool = False
    created_at: datetime


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    dimensions: List[DimensionIn]
    is_default: bool = False


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dimensions: Optional[List[DimensionIn]] = None
    is_default: Optional[bool] = None

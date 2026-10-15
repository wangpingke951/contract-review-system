"""app/schemas/review.py — 审查报告 Pydantic 模型"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ReviewCreate(BaseModel):
    contract_id: int


class RiskItemOut(BaseModel):
    id: int
    risk_level: str
    category_name: str
    contract_snippet: str
    issue: Optional[str] = None
    suggestion: Optional[str] = None
    is_positive: bool = False
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    source_knowledge_ids: Optional[list] = None


class ReviewOut(BaseModel):
    id: int
    contract_id: int
    overall_risk: Optional[str]
    status: str
    generated_at: datetime
    has_rag: bool = False
    risk_items: List[RiskItemOut] = []


class ReviewStatusOut(BaseModel):
    id: int
    status: str
    overall_risk: Optional[str] = None

"""app/schemas/review.py — 审查报告 Pydantic 模型"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ReviewCreate(BaseModel):
    contract_id: int
    template_id: Optional[int] = None


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
    # 人工处置状态（PRD P1）
    status: str = "pending"
    handled_at: Optional[datetime] = None


class RiskItemUpdate(BaseModel):
    """风险项处置动作"""
    status: str


class ReviewOut(BaseModel):
    id: int
    contract_id: int
    overall_risk: Optional[str]
    status: str
    generated_at: datetime
    has_rag: bool = False
    error_message: Optional[str] = None
    template_id: Optional[int] = None
    template_name: Optional[str] = None
    finalized_at: Optional[datetime] = None
    risk_items: List[RiskItemOut] = []


class ReviewStatusOut(BaseModel):
    id: int
    status: str
    overall_risk: Optional[str] = None
    error_message: Optional[str] = None
    item_count: int = 0

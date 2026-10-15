"""app/routers/reviews.py — 审查 API

POST /api/reviews            发起审查（同步执行，MVP）
GET  /api/reviews/{id}       报告详情（含风险项）
GET  /api/reviews/{id}/status 轻量状态查询
POST /api/reviews/{id}/retry  重试
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, TokenPayload
from app.services import review_service
from app.schemas.review import ReviewCreate, ReviewOut, ReviewStatusOut, RiskItemOut

router = APIRouter()


def _has_rag(items: list) -> bool:
    for it in items:
        try:
            if json.loads(it.source_knowledge_ids or "[]"):
                return True
        except (json.JSONDecodeError, TypeError):
            continue
    return False


@router.post("", response_model=ReviewOut)
async def create_review(
    body: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """发起审查（同步执行：检索 → LLM → 报告落库）"""
    is_admin = current.role.value == "admin"
    review = await review_service.create_review(db, body.contract_id, current.user_id, is_admin)
    review, items, _ = await review_service.get_review_with_items(
        db, review.id, current.user_id, is_admin
    )
    return _to_review_out(review, items)


def _to_item_out(i) -> RiskItemOut:
    try:
        src_ids = json.loads(i.source_knowledge_ids or "[]")
    except (json.JSONDecodeError, TypeError):
        src_ids = []
    return RiskItemOut(
        id=i.id,
        risk_level=i.risk_level.value,
        category_name=i.category_name,
        contract_snippet=i.contract_snippet,
        issue=i.issue,
        suggestion=i.suggestion,
        is_positive=i.is_positive,
        char_start=i.char_start,
        char_end=i.char_end,
        source_knowledge_ids=src_ids,
    )


def _to_review_out(review, items) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        contract_id=review.contract_id,
        overall_risk=review.overall_risk.value if review.overall_risk else None,
        status=review.status.value,
        generated_at=review.generated_at,
        has_rag=_has_rag(items),
        risk_items=[_to_item_out(i) for i in items],
    )


@router.get("/by-contract/{contract_id}", response_model=ReviewStatusOut)
async def get_review_by_contract(
    contract_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """按合同 ID 查审查报告（用于历史列表跳转）"""
    is_admin = current.role.value == "admin"
    review = await review_service.get_review_by_contract(
        db, contract_id, current.user_id, is_admin
    )
    return ReviewStatusOut(
        id=review.id,
        status=review.status.value,
        overall_risk=review.overall_risk.value if review.overall_risk else None,
    )


@router.get("/{review_id}", response_model=ReviewOut)
async def get_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    is_admin = current.role.value == "admin"
    review, items, _ = await review_service.get_review_with_items(
        db, review_id, current.user_id, is_admin
    )
    return ReviewOut(
        id=review.id,
        contract_id=review.contract_id,
        overall_risk=review.overall_risk.value if review.overall_risk else None,
        status=review.status.value,
        generated_at=review.generated_at,
        has_rag=_has_rag(items),
        risk_items=[_to_item_out(i) for i in items],
    )


@router.get("/{review_id}/status", response_model=ReviewStatusOut)
async def get_review_status(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    is_admin = current.role.value == "admin"
    review, _, _ = await review_service.get_review_with_items(
        db, review_id, current.user_id, is_admin
    )
    return ReviewStatusOut(
        id=review.id,
        status=review.status.value,
        overall_risk=review.overall_risk.value if review.overall_risk else None,
    )


@router.post("/{review_id}/retry", response_model=ReviewOut)
async def retry_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    is_admin = current.role.value == "admin"
    await review_service.retry_review(db, review_id, current.user_id, is_admin)
    review, items, _ = await review_service.get_review_with_items(
        db, review_id, current.user_id, is_admin
    )
    return ReviewOut(
        id=review.id,
        contract_id=review.contract_id,
        overall_risk=review.overall_risk.value if review.overall_risk else None,
        status=review.status.value,
        generated_at=review.generated_at,
        has_rag=_has_rag(items),
        risk_items=[_to_item_out(i) for i in items],
    )

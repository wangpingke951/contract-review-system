"""app/routers/reviews.py — 审查 API

POST   /api/reviews                       发起审查（异步：立即返回 running，前端轮询）
GET    /api/reviews/{id}                  报告详情（含风险项）
GET    /api/reviews/{id}/status           轻量状态查询（轮询用）
GET    /api/reviews/by-contract/{cid}     按合同查报告状态
POST   /api/reviews/{id}/retry            重新审查
PATCH  /api/reviews/{id}/items/{item_id}  风险项处置（确认/忽略/待改）
GET    /api/reviews/{id}/export           导出 Word 报告
"""
from __future__ import annotations

import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, TokenPayload
from app.core.exceptions import AppError
from app.core.rate_limit import review_limiter
from app.models.audit import ACTION_REVIEW_CREATE, ACTION_REVIEW_ITEM_HANDLE, ACTION_REVIEW_RETRY
from app.services import review_service, audit_service, export_service
from app.schemas.review import (
    ReviewCreate,
    ReviewOut,
    ReviewStatusOut,
    RiskItemOut,
    RiskItemUpdate,
)

settings = get_settings()

router = APIRouter()


def _has_rag(items: list) -> bool:
    for it in items:
        try:
            if json.loads(it.source_knowledge_ids or "[]"):
                return True
        except (json.JSONDecodeError, TypeError):
            continue
    return False


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
        status=i.status.value if getattr(i, "status", None) else "pending",
        handled_at=getattr(i, "handled_at", None),
    )


def _to_review_out(review, items) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        contract_id=review.contract_id,
        overall_risk=review.overall_risk.value if review.overall_risk else None,
        status=review.status.value,
        generated_at=review.generated_at,
        has_rag=_has_rag(items),
        error_message=getattr(review, "error_message", None),
        template_id=getattr(review, "template_id", None),
        template_name=getattr(review, "template_name", None),
        finalized_at=getattr(review, "finalized_at", None),
        risk_items=[_to_item_out(i) for i in items],
    )


@router.post("", response_model=ReviewOut)
async def create_review(
    body: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """发起审查：立即返回 running，真正的检索与 LLM 在后台执行"""
    is_admin = current.role.value == "admin"

    allowed, wait = review_limiter.allow(
        f"review:{current.user_id}", settings.RATE_LIMIT_REVIEW_PER_MINUTE
    )
    if not allowed:
        raise AppError(
            f"发起审查过于频繁（每分钟最多 {settings.RATE_LIMIT_REVIEW_PER_MINUTE} 次），"
            f"请 {wait} 秒后再试",
            code=429,
        )

    review = await review_service.create_review(
        db, body.contract_id, current.user_id, is_admin, template_id=body.template_id
    )
    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_REVIEW_CREATE,
        target_type="contract",
        target_id=body.contract_id,
        detail=f"review_id={review.id}",
        commit=True,
    )
    return _to_review_out(review, [])


@router.get("/by-contract/{contract_id}", response_model=ReviewStatusOut)
async def get_review_by_contract(
    contract_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """按合同 ID 查审查报告状态（历史列表跳转 + 轮询）"""
    is_admin = current.role.value == "admin"
    review = await review_service.get_review_by_contract(
        db, contract_id, current.user_id, is_admin
    )
    return ReviewStatusOut(
        id=review.id,
        status=review.status.value,
        overall_risk=review.overall_risk.value if review.overall_risk else None,
        error_message=getattr(review, "error_message", None),
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
    return _to_review_out(review, items)


@router.get("/{review_id}/status", response_model=ReviewStatusOut)
async def get_review_status(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    is_admin = current.role.value == "admin"
    review, items, _ = await review_service.get_review_with_items(
        db, review_id, current.user_id, is_admin
    )
    return ReviewStatusOut(
        id=review.id,
        status=review.status.value,
        overall_risk=review.overall_risk.value if review.overall_risk else None,
        error_message=getattr(review, "error_message", None),
        item_count=len(items),
    )


@router.post("/{review_id}/retry", response_model=ReviewOut)
async def retry_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    is_admin = current.role.value == "admin"
    review = await review_service.retry_review(
        db, review_id, current.user_id, is_admin
    )
    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_REVIEW_RETRY,
        target_type="review",
        target_id=review_id,
        detail=f"contract_id={review.contract_id}",
        commit=True,
    )
    return _to_review_out(review, [])


@router.post("/{review_id}/finalize", response_model=ReviewOut)
async def finalize_review(
    review_id: int,
    finalize: bool = True,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """
    报告定稿 / 取消定稿（?finalize=false 为取消）

    定稿后风险项锁定、不可重新审查；导出报告会带定稿信息。
    """
    is_admin = current.role.value == "admin"
    await review_service.finalize_review(
        db, review_id, current.user_id, is_admin, finalize=finalize
    )
    review, items, _ = await review_service.get_review_with_items(
        db, review_id, current.user_id, is_admin
    )
    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action="review.finalize" if finalize else "review.unfinalize",
        target_type="review",
        target_id=review_id,
        detail="定稿" if finalize else "取消定稿",
        commit=True,
    )
    return _to_review_out(review, items)


@router.patch("/{review_id}/items/{item_id}", response_model=RiskItemOut)
async def update_item_status(
    review_id: int,
    item_id: int,
    body: RiskItemUpdate,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """风险项处置：pending / confirmed / ignored / todo"""
    is_admin = current.role.value == "admin"
    item = await review_service.update_item_status(
        db, review_id, item_id, body.status, current.user_id, is_admin
    )
    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_REVIEW_ITEM_HANDLE,
        target_type="risk_item",
        target_id=item_id,
        detail=f"status={item.status.value}",
        commit=True,
    )
    return _to_item_out(item)


@router.get("/{review_id}/export")
async def export_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """导出 Word 报告"""
    is_admin = current.role.value == "admin"
    review, items, contract = await review_service.get_review_with_items(
        db, review_id, current.user_id, is_admin
    )
    content = export_service.build_review_docx(review, items, contract)
    filename = f"审查报告_{contract.filename.rsplit('.', 1)[0]}.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )

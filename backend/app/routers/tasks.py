"""
app/routers/tasks.py — 任务中心

GET  /api/tasks                 审查任务总览（进行中 / 失败 / 待审查 / 解析失败）
POST /api/tasks/batch-review    批量发起审查
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, TokenPayload
from app.core.exceptions import ValidationError
from app.models.contract import Contract, ContractStatus
from app.models.review import Review, ReviewStatus
from app.services import review_service

router = APIRouter()

MAX_BATCH = 20


class BatchReviewIn(BaseModel):
    contract_ids: list[int]
    template_id: int | None = None


def _task_item(contract: Contract, review: Review | None) -> dict:
    return {
        "contract_id": contract.id,
        "filename": contract.filename,
        "version": contract.version or 1,
        "contract_status": contract.status.value,
        "review_id": review.id if review else None,
        "review_status": review.status.value if review else None,
        "overall_risk": review.overall_risk.value if review and review.overall_risk else None,
        "error_message": review.error_message if review else contract.parse_error,
        "template_name": review.template_name if review else None,
        "finalized": bool(review and review.finalized_at),
        "created_at": contract.created_at,
    }


@router.get("")
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """把合同 + 审查报告合并成任务视图，按状态分组"""
    is_admin = current.role.value == "admin"
    stmt = select(Contract, Review).outerjoin(Review, Review.contract_id == Contract.id)
    if not is_admin:
        stmt = stmt.where(Contract.uploader_id == current.user_id)
    stmt = stmt.order_by(Contract.created_at.desc())

    rows = (await db.execute(stmt)).all()

    groups: dict[str, list[dict]] = {
        "running": [], "failed": [], "pending": [], "parse_failed": [],
    }
    for contract, review in rows:
        item = _task_item(contract, review)
        if contract.status == ContractStatus.REVIEWING or (
            review and review.status == ReviewStatus.RUNNING
        ):
            groups["running"].append(item)
        elif contract.status == ContractStatus.REVIEW_FAILED or (
            review and review.status == ReviewStatus.FAILED
        ):
            groups["failed"].append(item)
        elif contract.status == ContractStatus.PARSED:
            groups["pending"].append(item)
        elif contract.status == ContractStatus.PARSING_FAILED:
            groups["parse_failed"].append(item)

    return {
        "summary": {k: len(v) for k, v in groups.items()},
        "total": len(rows),
        **groups,
    }


@router.post("/batch-review")
async def batch_review(
    body: BatchReviewIn,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """批量发起审查：逐个提交，单个失败不影响其余"""
    ids = list(dict.fromkeys(body.contract_ids))  # 去重保序
    if not ids:
        raise ValidationError("请至少选择一份合同")
    if len(ids) > MAX_BATCH:
        raise ValidationError(f"一次最多批量审查 {MAX_BATCH} 份合同")

    is_admin = current.role.value == "admin"
    accepted: list[dict] = []
    skipped: list[dict] = []

    for cid in ids:
        try:
            review = await review_service.create_review(
                db, cid, current.user_id, is_admin, template_id=body.template_id
            )
            accepted.append({"contract_id": cid, "review_id": review.id})
        except Exception as e:
            skipped.append({"contract_id": cid, "reason": getattr(e, "message", str(e))})

    return {"accepted": accepted, "skipped": skipped}

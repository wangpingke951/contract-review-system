"""
app/services/review_service.py — 审查业务逻辑

MVP 同步执行（无 Celery）：POST 请求内完成 检索 → LLM → 落库。
LLM 调用是 async httpx，不阻塞事件循环，可并发服务多个请求。
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError, PermissionError, ValidationError, AppError
from app.models.contract import Contract, ContractStatus
from app.models.review import Review, RiskItem, OverallRisk, ReviewStatus, RiskLevel
from app.models.category import RiskCategory
from app.rag.review_chain import run_review

settings = get_settings()


async def create_review(
    db: AsyncSession,
    contract_id: int,
    user_id: int,
    is_admin: bool = False,
) -> Review:
    """发起审查并同步执行完整流程"""
    # 1) 加载合同 + 权限
    contract = (await db.execute(select(Contract).where(Contract.id == contract_id))).scalar_one_or_none()
    if not contract:
        raise NotFoundError("合同不存在")
    if not is_admin and contract.uploader_id != user_id:
        raise PermissionError("无权审查此合同")
    if not contract.parsed_content:
        raise ValidationError("合同尚未完成解析，无法审查")

    # 2) 同一合同已有报告时先删除旧报告（重新审查覆盖）
    old = (await db.execute(select(Review).where(Review.contract_id == contract_id))).scalar_one_or_none()
    if old:
        await db.delete(old)
        await db.flush()

    # 3) 执行审查（检索 + LLM），带超时保护
    try:
        report = await asyncio.wait_for(
            run_review(contract.parsed_content),
            timeout=settings.REVIEW_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise AppError(
            f"审查超时（超过 {settings.REVIEW_TIMEOUT_SECONDS} 秒未完成），"
            f"合同篇幅可能过长，请稍后在历史记录中重试",
            code=504,
        )
    except Exception as e:
        # 审查失败也留痕（不创建失败记录，直接抛错由前端提示重试）
        raise AppError(f"审查执行失败: {e}", code=502)

    # 4) 落库：Review + RiskItems（类别快照 + 类别 ID 匹配）
    review = Review(
        contract_id=contract_id,
        overall_risk=OverallRisk(report["overall_risk"]),
        status=ReviewStatus.DONE,
    )
    db.add(review)
    await db.flush()

    # 类别名 → ID 映射（管理员配置的类别）
    cats = (await db.execute(select(RiskCategory))).scalars().all()
    cat_map = {c.name: c.id for c in cats}

    for item in report["risk_items"]:
        db.add(RiskItem(
            review_id=review.id,
            risk_level=RiskLevel(item["risk_level"]),
            category_id=cat_map.get(item.get("category_name")),
            category_name=item.get("category_name", "其他"),
            contract_snippet=item.get("contract_snippet", ""),
            issue=item.get("issue"),
            suggestion=item.get("suggestion"),
            is_positive=item.get("is_positive", False),
            source_knowledge_ids=json.dumps(item.get("source_knowledge_ids", []), ensure_ascii=False),
        ))

    # 合同状态推进
    contract.status = ContractStatus.REVIEW_DONE
    await db.commit()
    await db.refresh(review)
    return review


async def get_review_with_items(
    db: AsyncSession,
    review_id: int,
    user_id: int,
    is_admin: bool = False,
) -> tuple[Review, list[RiskItem], Contract]:
    review = (await db.execute(select(Review).where(Review.id == review_id))).scalar_one_or_none()
    if not review:
        raise NotFoundError("审查报告不存在")
    contract = (await db.execute(select(Contract).where(Contract.id == review.contract_id))).scalar_one()
    if not is_admin and contract.uploader_id != user_id:
        raise PermissionError("无权查看此报告")
    items = list((
        await db.execute(select(RiskItem).where(RiskItem.review_id == review_id).order_by(RiskItem.id))
    ).scalars().all())
    return review, items, contract


async def get_review_by_contract(
    db: AsyncSession,
    contract_id: int,
    user_id: int,
    is_admin: bool = False,
) -> Review:
    """按合同 ID 查审查报告（历史列表跳转用）"""
    contract = (await db.execute(select(Contract).where(Contract.id == contract_id))).scalar_one_or_none()
    if not contract:
        raise NotFoundError("合同不存在")
    if not is_admin and contract.uploader_id != user_id:
        raise PermissionError("无权访问此合同")
    review = (await db.execute(select(Review).where(Review.contract_id == contract_id))).scalar_one_or_none()
    if not review:
        raise NotFoundError("该合同尚未生成审查报告")
    return review


async def retry_review(
    db: AsyncSession,
    review_id: int,
    user_id: int,
    is_admin: bool = False,
) -> Review:
    """重试 = 重新执行一次审查（覆盖旧报告）"""
    review = (await db.execute(select(Review).where(Review.id == review_id))).scalar_one_or_none()
    if not review:
        raise NotFoundError("审查报告不存在")
    return await create_review(db, review.contract_id, user_id, is_admin)

"""
app/services/review_service.py — 审查业务逻辑

执行模型（PRD 5.4：后台异步，用户可离开页面）：
- create_review 只做校验 + 落一条 status=running 的 Review（以及把合同置为 reviewing），
  然后按 REVIEW_EXECUTION_MODE 派发真正的审查任务，立即返回；
- execute_review 在独立 DB session 中跑 检索 → LLM → 落库，前端轮询状态；
- 失败/超时写 status=failed + error_message，可重试。

REVIEW_EXECUTION_MODE:
- background（默认）：asyncio 后台任务，本地开发无需 Redis
- celery：交给 Celery worker（Docker 部署）
- inline：请求内同步执行，仅调试用
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError, PermissionError, ValidationError
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
    template_id: int | None = None,
) -> Review:
    """发起审查：落 running 记录后后台执行，立即返回"""
    # 1) 加载合同 + 权限
    # with_for_update：同一合同并发发起审查时串行化，避免撞 contract_id 唯一约束
    contract = (await db.execute(
        select(Contract).where(Contract.id == contract_id).with_for_update()
    )).scalar_one_or_none()
    if not contract:
        raise NotFoundError("合同不存在")
    if not is_admin and contract.uploader_id != user_id:
        raise PermissionError("无权审查此合同")
    if not contract.parsed_content:
        raise ValidationError("合同尚未完成解析，无法审查")

    # 2) 已有审查在跑：直接返回，避免重复触发（PRD 5.4 排队语义的最简实现）
    existing = (await db.execute(
        select(Review).where(Review.contract_id == contract_id)
    )).scalar_one_or_none()
    if existing and existing.status == ReviewStatus.RUNNING:
        return existing

    # 3) 已定稿的报告不允许覆盖重审
    if existing and existing.finalized_at:
        raise ValidationError("该报告已定稿，如需重新审查请先取消定稿")

    # 4) 解析审查模板（不传则用默认模板）
    from app.services import template_service
    _, tpl = await template_service.resolve_dimensions(db, template_id)
    if template_id and not tpl:
        raise ValidationError("指定的审查模板不存在")

    # 5) 旧报告（已完成/失败）先删除，重新审查覆盖
    if existing:
        await db.delete(existing)
        await db.flush()

    # 6) 落 running 记录
    review = Review(
        contract_id=contract_id,
        overall_risk=None,
        status=ReviewStatus.RUNNING,
        template_id=tpl.id if tpl else None,
        template_name=tpl.name if tpl else None,
    )
    db.add(review)
    contract.status = ContractStatus.REVIEWING
    await db.commit()
    await db.refresh(review)

    # 7) 派发执行
    await _dispatch(review.id, contract_id)
    return review


async def _dispatch(review_id: int, contract_id: int) -> None:
    """按配置选择执行方式"""
    mode = (settings.REVIEW_EXECUTION_MODE or "background").lower()

    if mode == "celery":
        try:
            from app.celery_tasks.tasks import execute_review_task
            execute_review_task.delay(review_id, contract_id)
            return
        except Exception:
            # Celery/Redis 不可用时退回进程内后台任务，保证功能不中断
            asyncio.create_task(execute_review(review_id, contract_id))
            return

    if mode == "inline":
        await execute_review(review_id, contract_id)
        return

    asyncio.create_task(execute_review(review_id, contract_id))


async def execute_review(review_id: int, contract_id: int) -> None:
    """
    真正的审查执行体。必须使用独立 session ——
    它可能跑在请求结束之后（background 模式）。
    """
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        review = (await db.execute(
            select(Review).where(Review.id == review_id)
        )).scalar_one_or_none()
        contract = (await db.execute(
            select(Contract).where(Contract.id == contract_id)
        )).scalar_one_or_none()
        if not review or not contract:
            return

        try:
            from app.services import template_service, usage_service
            from app.llm.factory import get_llm
            import time as _time

            dims, _ = await template_service.resolve_dimensions(db, review.template_id)
            started = _time.monotonic()
            report = await asyncio.wait_for(
                run_review(contract.parsed_content, dims),
                timeout=settings.REVIEW_TIMEOUT_SECONDS,
            )
            elapsed_ms = int((_time.monotonic() - started) * 1000)
            llm = get_llm()
            await usage_service.record(
                db,
                user_id=contract.uploader_id,
                scene="review",
                model=getattr(llm, "model", "") or settings.LLM_MODEL,
                usage=getattr(llm, "last_usage", {}) or {},
                duration_ms=elapsed_ms,
                success=True,
            )
        except asyncio.TimeoutError:
            await _mark_failed(
                db, review, contract,
                f"审查超时（超过 {settings.REVIEW_TIMEOUT_SECONDS} 秒未完成），"
                f"合同篇幅可能过长，请稍后重试",
            )
            return
        except Exception as e:
            await _mark_failed(db, review, contract, f"审查执行失败: {e}")
            return

        try:
            # 落库：Review + RiskItems（类别快照 + 类别 ID 匹配）
            review.overall_risk = OverallRisk(report["overall_risk"])
            review.status = ReviewStatus.DONE
            review.error_message = None

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
                    source_knowledge_ids=json.dumps(
                        item.get("source_knowledge_ids", []), ensure_ascii=False
                    ),
                ))

            contract.status = ContractStatus.REVIEW_DONE
            await db.commit()
        except Exception as e:
            await db.rollback()
            await _mark_failed(db, review, contract, f"审查结果落库失败: {e}")


async def _mark_failed(db: AsyncSession, review: Review, contract: Contract, message: str) -> None:
    review.status = ReviewStatus.FAILED
    review.error_message = message
    contract.status = ContractStatus.REVIEW_FAILED
    try:
        from app.services import usage_service
        await usage_service.record(
            db,
            user_id=contract.uploader_id,
            scene="review",
            model=settings.LLM_MODEL,
            usage={},
            duration_ms=0,
            success=False,
        )
        await db.commit()
    except Exception:
        await db.rollback()


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
    """重试 = 重新执行一次审查（沿用原审查模板）"""
    review = (await db.execute(select(Review).where(Review.id == review_id))).scalar_one_or_none()
    if not review:
        raise NotFoundError("审查报告不存在")
    return await create_review(
        db, review.contract_id, user_id, is_admin, template_id=review.template_id
    )


async def finalize_review(
    db: AsyncSession,
    review_id: int,
    user_id: int,
    is_admin: bool = False,
    finalize: bool = True,
) -> Review:
    """
    报告定稿 / 取消定稿（PRD Q1 审批流的轻量版）

    定稿后风险项锁定、不允许重新审查，导出报告会带上定稿时间与定稿人。
    """
    from datetime import datetime

    review = (await db.execute(select(Review).where(Review.id == review_id))).scalar_one_or_none()
    if not review:
        raise NotFoundError("审查报告不存在")

    contract = (await db.execute(
        select(Contract).where(Contract.id == review.contract_id)
    )).scalar_one()
    if not is_admin and contract.uploader_id != user_id:
        raise PermissionError("无权操作此报告")

    if finalize:
        if review.status != ReviewStatus.DONE:
            raise ValidationError("只有审查完成的报告才能定稿")
        review.finalized_at = datetime.now()
        review.finalized_by = user_id
    else:
        review.finalized_at = None
        review.finalized_by = None

    await db.commit()
    await db.refresh(review)
    return review


async def update_item_status(
    db: AsyncSession,
    review_id: int,
    item_id: int,
    status: str,
    user_id: int,
    is_admin: bool = False,
) -> RiskItem:
    """更新单条风险项的人工处置状态（PRD P1）"""
    from app.models.review import RiskItemStatus
    from datetime import datetime

    review = (await db.execute(select(Review).where(Review.id == review_id))).scalar_one_or_none()
    if not review:
        raise NotFoundError("审查报告不存在")
    if review.finalized_at:
        raise ValidationError("报告已定稿，如需修改请先取消定稿")

    contract = (await db.execute(
        select(Contract).where(Contract.id == review.contract_id)
    )).scalar_one()
    if not is_admin and contract.uploader_id != user_id:
        raise PermissionError("无权修改此报告")

    item = (await db.execute(
        select(RiskItem).where(RiskItem.id == item_id, RiskItem.review_id == review_id)
    )).scalar_one_or_none()
    if not item:
        raise NotFoundError("风险项不存在")

    try:
        item.status = RiskItemStatus(status)
    except ValueError:
        valid = [s.value for s in RiskItemStatus]
        raise ValidationError(f"status 必须是 {valid} 之一")

    item.handled_at = datetime.now()
    await db.commit()
    await db.refresh(item)
    return item

"""
app/services/template_service.py — 审查模板

默认模板 = 项目原有的 9 个审查维度（PRD 4.3 风险类别），
管理员可另建「采购合同」「劳动合同」等模板，发起审查时选用。
"""
from __future__ import annotations

import json

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.template import ReviewTemplate
from app.rag.retriever import REVIEW_DIMENSIONS

DEFAULT_TEMPLATE_NAME = "通用合同审查"

DEFAULT_DESCRIPTION = "覆盖条款缺失、金额、期限、主体、违约、知产、保密、不可抗力、争议解决九类通用风险"


def _default_dimensions() -> list[dict]:
    return [{"name": name, "prompt": prompt, "weight": 1} for name, prompt in REVIEW_DIMENSIONS]


async def ensure_default_template(db: AsyncSession) -> None:
    """幂等：没有任何模板时建一个默认模板"""
    total = (await db.execute(select(func.count(ReviewTemplate.id)))).scalar() or 0
    if total:
        return
    db.add(ReviewTemplate(
        name=DEFAULT_TEMPLATE_NAME,
        description=DEFAULT_DESCRIPTION,
        dimensions=json.dumps(_default_dimensions(), ensure_ascii=False),
        is_default=True,
    ))
    await db.commit()


def parse_dimensions(raw: str) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        raise ValidationError("模板维度数据损坏")
    return data if isinstance(data, list) else []


def _validate_dimensions(dimensions: list[dict]) -> list[dict]:
    if not dimensions:
        raise ValidationError("模板至少需要 1 个审查维度")
    if len(dimensions) > 20:
        raise ValidationError("审查维度不能超过 20 个")
    cleaned = []
    for d in dimensions:
        name = (d.get("name") or "").strip()
        prompt = (d.get("prompt") or "").strip()
        if not name:
            raise ValidationError("维度名称不能为空")
        if len(name) > 64:
            raise ValidationError(f"维度名称过长：{name[:20]}…")
        if not prompt:
            raise ValidationError(f"维度「{name}」缺少审查说明")
        cleaned.append({"name": name, "prompt": prompt, "weight": int(d.get("weight") or 1)})
    return cleaned


async def list_templates(db: AsyncSession) -> list[ReviewTemplate]:
    rows = await db.execute(
        select(ReviewTemplate).order_by(ReviewTemplate.is_default.desc(), ReviewTemplate.id)
    )
    return list(rows.scalars().all())


async def get_template(db: AsyncSession, template_id: int) -> ReviewTemplate:
    tpl = (await db.execute(
        select(ReviewTemplate).where(ReviewTemplate.id == template_id)
    )).scalar_one_or_none()
    if not tpl:
        raise NotFoundError("审查模板不存在")
    return tpl


async def get_default_template(db: AsyncSession) -> ReviewTemplate | None:
    tpl = (await db.execute(
        select(ReviewTemplate).where(ReviewTemplate.is_default.is_(True))
    )).scalars().first()
    if tpl:
        return tpl
    rows = await db.execute(select(ReviewTemplate).order_by(ReviewTemplate.id))
    return rows.scalars().first()


async def resolve_dimensions(db: AsyncSession, template_id: int | None) -> tuple[list[tuple[str, str]], ReviewTemplate | None]:
    """
    发起审查时解析出实际使用的维度列表 [(name, prompt)]。
    template_id 为空 → 用默认模板；没有任何模板 → 回落到代码内置维度。
    """
    tpl = await get_template(db, template_id) if template_id else await get_default_template(db)
    if not tpl:
        return list(REVIEW_DIMENSIONS), None

    dims = [
        (d["name"], d.get("prompt") or "")
        for d in parse_dimensions(tpl.dimensions)
        if d.get("name")
    ]
    return (dims or list(REVIEW_DIMENSIONS)), tpl


async def create_template(db: AsyncSession, name: str, description: str,
                          dimensions: list[dict], is_default: bool, admin_id: int) -> ReviewTemplate:
    name = (name or "").strip()
    if not name:
        raise ValidationError("模板名称不能为空")
    exists = (await db.execute(
        select(func.count(ReviewTemplate.id)).where(ReviewTemplate.name == name)
    )).scalar()
    if exists:
        raise ValidationError(f"模板「{name}」已存在")

    dims = _validate_dimensions(dimensions)
    if is_default:
        for t in (await db.execute(select(ReviewTemplate))).scalars().all():
            t.is_default = False

    tpl = ReviewTemplate(
        name=name,
        description=(description or "").strip() or None,
        dimensions=json.dumps(dims, ensure_ascii=False),
        is_default=is_default,
        created_by=admin_id,
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def update_template(db: AsyncSession, template_id: int, name: str | None,
                          description: str | None, dimensions: list[dict] | None,
                          is_default: bool | None) -> ReviewTemplate:
    tpl = await get_template(db, template_id)

    if name is not None:
        name = name.strip()
        if not name:
            raise ValidationError("模板名称不能为空")
        dup = (await db.execute(
            select(func.count(ReviewTemplate.id)).where(
                ReviewTemplate.name == name, ReviewTemplate.id != template_id
            )
        )).scalar()
        if dup:
            raise ValidationError(f"模板「{name}」已存在")
        tpl.name = name

    if description is not None:
        tpl.description = description.strip() or None

    if dimensions is not None:
        tpl.dimensions = json.dumps(_validate_dimensions(dimensions), ensure_ascii=False)

    if is_default:
        for t in (await db.execute(select(ReviewTemplate))).scalars().all():
            t.is_default = (t.id == template_id)
    elif is_default is False:
        tpl.is_default = False

    await db.commit()
    await db.refresh(tpl)
    return tpl


async def delete_template(db: AsyncSession, template_id: int) -> None:
    tpl = await get_template(db, template_id)
    total = (await db.execute(select(func.count(ReviewTemplate.id)))).scalar() or 0
    if total <= 1:
        raise ValidationError("至少需要保留 1 个审查模板，无法删除")
    await db.delete(tpl)
    await db.commit()

"""
app/routers/templates.py — 审查模板

GET    /api/templates            列表（登录用户可读，发起审查时选用）
POST   /api/templates            新建（管理员）
PUT    /api/templates/{id}       修改（管理员）
DELETE /api/templates/{id}       删除（管理员，至少保留 1 个）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_admin, get_current_user, TokenPayload
from app.services import template_service
from app.schemas.template import TemplateOut, TemplateCreate, TemplateUpdate

router = APIRouter()


def _to_out(tpl) -> TemplateOut:
    return TemplateOut(
        id=tpl.id,
        name=tpl.name,
        description=tpl.description,
        dimensions=template_service.parse_dimensions(tpl.dimensions),
        is_default=tpl.is_default,
        created_at=tpl.created_at,
    )


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    rows = await template_service.list_templates(db)
    return [_to_out(t) for t in rows]


@router.post("", response_model=TemplateOut)
async def create_template(
    body: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    tpl = await template_service.create_template(
        db,
        name=body.name,
        description=body.description or "",
        dimensions=[d.model_dump() for d in body.dimensions],
        is_default=body.is_default,
        admin_id=current.user_id,
    )
    return _to_out(tpl)


@router.put("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: int,
    body: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    tpl = await template_service.update_template(
        db,
        template_id,
        name=body.name,
        description=body.description,
        dimensions=[d.model_dump() for d in body.dimensions] if body.dimensions is not None else None,
        is_default=body.is_default,
    )
    return _to_out(tpl)


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    await template_service.delete_template(db, template_id)
    return {"code": 0, "message": "删除成功", "data": None}

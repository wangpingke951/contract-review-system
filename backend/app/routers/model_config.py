"""
app/routers/model_config.py — 模型配置（管理员）

GET  /api/admin/model-config           当前生效配置（密钥掩码）
PUT  /api/admin/model-config           保存并即时生效，无需重启
POST /api/admin/model-config/test      连通性测试（真实发一次最小请求）
GET  /api/admin/model-config/providers 可选提供商与推荐模型（前端下拉）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_admin, TokenPayload
from app.services import config_service
from app.schemas.model_config import (
    ModelConfigOut,
    ModelConfigIn,
    ConnectionTestIn,
    ConnectionTestOut,
)

router = APIRouter()


@router.get("", response_model=ModelConfigOut)
async def get_model_config(
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    cfg = await config_service.reload(db)
    return ModelConfigOut(**config_service.public_view(cfg))


@router.put("", response_model=ModelConfigOut)
async def update_model_config(
    body: ModelConfigIn,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    cfg = await config_service.update(db, body.model_dump(exclude_unset=True), current.user_id)
    return ModelConfigOut(**config_service.public_view(cfg))


@router.post("/test", response_model=ConnectionTestOut)
async def test_model_connection(
    body: ConnectionTestIn,
    current: TokenPayload = Depends(get_current_admin),
):
    result = await config_service.test_connection(
        provider=body.provider,
        api_key=body.api_key,
        model=body.model,
        base_url=body.base_url,
        kind=body.kind,
    )
    return ConnectionTestOut(**result)


@router.get("/providers")
async def list_providers(
    current: TokenPayload = Depends(get_current_admin),
):
    return config_service.PROVIDERS

"""app/routers/contracts.py — 合同 API

POST   /api/contracts/upload       上传 + 解析
GET    /api/contracts              列表（支持分页）
GET    /api/contracts/{id}         详情
DELETE /api/contracts/{id}         删除
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, TokenPayload
from app.models.contract import Contract
from app.services import contract_service
from app.schemas.contract import (
    ContractUploadResponse,
    ContractListItem,
    ContractListResponse,
    ContractDetailResponse,
)

router = APIRouter()


@router.post("/upload", response_model=ContractUploadResponse)
async def upload_contract(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """上传合同 → 自动解析 → 返回结构化章节

    解析失败不会抛异常，而是返回 status=parsing_failed + parse_error，
    便于前端在文件列表中逐条展示原因（批量上传时互不影响）。
    """
    contract = await contract_service.upload_and_parse(
        db=db, file=file, uploader_id=current.user_id
    )

    # 转换为响应
    parsed_sections = []
    if contract.parsed_sections:
        import json
        parsed_sections = json.loads(contract.parsed_sections)

    return ContractUploadResponse(
        id=contract.id,
        filename=contract.filename,
        file_type=contract.file_type,
        status=contract.status.value,
        word_count=len(contract.parsed_content or ""),
        language="zh-CN",
        sections=parsed_sections,
        parse_errors=[contract.parse_error] if contract.parse_error else [],
        parse_error=contract.parse_error,
    )


@router.get("", response_model=ContractListResponse)
async def list_contracts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    contracts = await contract_service.list_by_user(
        db=db, user_id=current.user_id, page=page, size=size,
        is_admin=current.role.value == "admin",
    )
    items = [
        ContractListItem(
            id=c.id,
            filename=c.filename,
            file_type=c.file_type,
            status=c.status.value,
            created_at=c.created_at,
            parse_error=c.parse_error,
        )
        for c in contracts
    ]
    return ContractListResponse(items=items, total=len(items))


@router.get("/{contract_id}", response_model=ContractDetailResponse)
async def get_contract(
    contract_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    contract = await contract_service.get_by_id(db, contract_id)
    if not contract:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("合同不存在")

    # 权限：普通用户只能看自己的；管理员看全部
    if current.role.value != "admin" and contract.uploader_id != current.user_id:
        from app.core.exceptions import PermissionError
        raise PermissionError("无权查看此合同")

    parsed_sections = None
    if contract.parsed_sections:
        import json
        parsed_sections = json.loads(contract.parsed_sections)

    return ContractDetailResponse(
        id=contract.id,
        filename=contract.filename,
        file_type=contract.file_type,
        status=contract.status.value,
        parsed_content=contract.parsed_content,
        parsed_sections=parsed_sections,
        parse_error=contract.parse_error,
        created_at=contract.created_at,
        uploader_id=contract.uploader_id,
    )


@router.delete("/{contract_id}")
async def delete_contract(
    contract_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    contract = await contract_service.get_by_id(db, contract_id)
    if not contract:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("合同不存在")
    if current.role.value != "admin" and contract.uploader_id != current.user_id:
        from app.core.exceptions import PermissionError
        raise PermissionError("无权删除此合同")

    await contract_service.delete_contract(db, contract)
    return {"code": 0, "message": "删除成功", "data": None}

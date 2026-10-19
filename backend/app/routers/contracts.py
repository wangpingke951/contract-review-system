"""app/routers/contracts.py — 合同 API

POST   /api/contracts/upload       上传 + 解析
GET    /api/contracts              列表（支持分页）
GET    /api/contracts/{id}         详情
DELETE /api/contracts/{id}         删除
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, TokenPayload
from app.models.audit import ACTION_CONTRACT_DELETE, ACTION_CONTRACT_UPLOAD
from app.models.contract import Contract
from app.services import contract_service, audit_service
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
    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_CONTRACT_UPLOAD,
        target_type="contract",
        target_id=contract.id,
        detail=f"{contract.filename}（{contract.status.value}）",
        commit=True,
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
        version=contract.version or 1,
    )


@router.get("", response_model=ContractListResponse)
async def list_contracts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    is_admin = current.role.value == "admin"
    contracts = await contract_service.list_by_user(
        db=db, user_id=current.user_id, page=page, size=size, is_admin=is_admin,
    )
    total = await contract_service.count_by_user(
        db=db, user_id=current.user_id, is_admin=is_admin,
    )
    follow_ups = await contract_service.count_follow_ups(
        db, [c.id for c in contracts]
    )
    items = [
        ContractListItem(
            id=c.id,
            filename=c.filename,
            file_type=c.file_type,
            status=c.status.value,
            created_at=c.created_at,
            parse_error=c.parse_error,
            follow_up_count=follow_ups.get(c.id, 0),
            version=c.version or 1,
            root_contract_id=c.root_contract_id,
        )
        for c in contracts
    ]
    return ContractListResponse(items=items, total=total)


@router.post("/{contract_id}/versions", response_model=ContractUploadResponse)
async def upload_new_version(
    contract_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """上传同一份合同的新版本（旧版本保留，用于比对与问题闭环）"""
    contract = await contract_service.upload_new_version(
        db, contract_id, file, current.user_id, current.role.value == "admin"
    )
    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_CONTRACT_UPLOAD,
        target_type="contract",
        target_id=contract.id,
        detail=f"{contract.filename}（v{contract.version}，{contract.status.value}）",
        commit=True,
    )
    import json as _json
    sections = _json.loads(contract.parsed_sections) if contract.parsed_sections else []
    return ContractUploadResponse(
        id=contract.id,
        filename=contract.filename,
        file_type=contract.file_type,
        status=contract.status.value,
        word_count=len(contract.parsed_content or ""),
        language="zh-CN",
        sections=sections,
        parse_errors=[contract.parse_error] if contract.parse_error else [],
        parse_error=contract.parse_error,
        version=contract.version or 1,
    )


@router.get("/{contract_id}/diff")
async def contract_diff(
    contract_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_user),
):
    """
    与上一版本比对：段落级差异 + 上一版审查问题的闭环情况
    """
    from app.core.exceptions import PermissionError, ValidationError
    from app.models.review import Review, RiskItem
    from app.services import diff_service

    contract = await contract_service.get_by_id(db, contract_id)
    if not contract:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("合同不存在")
    if current.role.value != "admin" and contract.uploader_id != current.user_id:
        raise PermissionError("无权查看此合同")

    parent = None
    if contract.parent_contract_id:
        parent = await contract_service.get_by_id(db, contract.parent_contract_id)
    if not parent:
        # 没有显式 parent 时，找同族里 version 次大的一版
        root_id = contract.root_contract_id or contract.id
        rows = (await db.execute(
            select(Contract).where(
                (Contract.id == root_id) | (Contract.root_contract_id == root_id)
            ).order_by(Contract.version.desc())
        )).scalars().all()
        parent = next((c for c in rows if c.id != contract.id and c.version < contract.version), None)

    if not parent:
        raise ValidationError("这是首个版本，没有可对比的历史版本")

    text_diff = diff_service.diff_paragraphs(
        parent.parsed_content or "", contract.parsed_content or ""
    )

    # 上一版报告的风险项
    old_review = (await db.execute(
        select(Review).where(Review.contract_id == parent.id)
    )).scalar_one_or_none()
    old_items = []
    if old_review:
        old_items = list((await db.execute(
            select(RiskItem).where(RiskItem.review_id == old_review.id).order_by(RiskItem.id)
        )).scalars().all())

    closure = diff_service.check_closure(old_items, contract.parsed_content or "")

    return {
        "from": {
            "id": parent.id,
            "version": parent.version,
            "filename": parent.filename,
            "created_at": parent.created_at,
            "review_id": old_review.id if old_review else None,
        },
        "to": {
            "id": contract.id,
            "version": contract.version,
            "filename": contract.filename,
            "created_at": contract.created_at,
        },
        "text": text_diff,
        "issues": closure,
        "issue_summary": diff_service.summarize_closure(closure),
    }


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
        version=contract.version or 1,
        parent_contract_id=contract.parent_contract_id,
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

    deleted_id, deleted_name = contract.id, contract.filename
    await contract_service.delete_contract(db, contract)
    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_CONTRACT_DELETE,
        target_type="contract",
        target_id=deleted_id,
        detail=deleted_name,
        commit=True,
    )
    return {"code": 0, "message": "删除成功", "data": None}

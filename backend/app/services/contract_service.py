"""app/services/contract_service.py — 合同业务逻辑层

Phase 4 实现：
- upload_and_parse: 上传文件 → 保存到本地 → 调 parser 解析 → 写 MySQL
- list_by_user: 列表查询
- get_detail: 详情查询
- delete: 删除
"""
from __future__ import annotations

import os
import json
import shutil
from datetime import datetime
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.models.contract import Contract, ContractStatus
from app.parsers.factory import get_parser, supported_extensions

settings = get_settings()

# —— 文件扩展名 → file_type 映射 ——
_TYPE_MAP = {
    "pdf": "pdf",
    "docx": "docx",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
}


async def upload_and_parse(
    db: AsyncSession,
    file: UploadFile,
    uploader_id: int,
) -> Contract:
    """
    上传 + 解析（同步执行，Phase 6 改为 Celery 异步）

    流程：
    1. 校验文件类型和大小
    2. 保存到 UPLOAD_DIR/{uploader_id}/{timestamp}_{safe_filename}
    3. 调 parser 解析
    4. 中文检测 → 非中文阻断
    5. 写 DB
    """
    # —— 1. 校验 ——
    filename = file.filename or "unnamed"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = supported_extensions()
    if ext not in allowed:
        raise ValidationError(
            f"不支持的文件类型 .{ext}，允许: {sorted(allowed)}"
        )

    MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    # 先读一下检查大小（UploadFile 没有内置 size 属性）
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise ValidationError(
            f"文件超过 {settings.MAX_UPLOAD_SIZE_MB}MB 上限"
        )
    await file.seek(0)

    # —— 2. 保存 ——
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(uploader_id))
    os.makedirs(upload_dir, exist_ok=True)
    safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(filename)}"
    file_path = os.path.join(upload_dir, safe_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # —— 3. 写 DB（初始状态 parsing）——
    file_type = _TYPE_MAP.get(ext, ext)
    contract = Contract(
        filename=filename,
        file_type=file_type,
        file_path=file_path,
        status=ContractStatus.PARSING,
        uploader_id=uploader_id,
    )
    db.add(contract)
    await db.flush()  # 拿到 contract.id

    # —— 4. 解析 ——
    parser = get_parser(filename)
    result = await parser.parse(file_path)

    # —— 5. 中文检测 ——
    if result.language != "zh-CN" and result.word_count > 50:
        # 非中文合同，按 PRD 明确排除：提示用户
        contract.status = ContractStatus.PARSING_FAILED
        await db.commit()
        raise ValidationError(
            f"当前版本仅支持中文合同，检测到非中文文本（中文字符占比过低）"
        )

    # —— 6. 写回解析结果 ——
    if result.parse_errors:
        contract.status = ContractStatus.PARSING_FAILED
        contract.parsed_content = ""
    else:
        contract.status = ContractStatus.PARSED
        contract.parsed_content = result.raw_text
        contract.parsed_sections = json.dumps(
            [s.__dict__ for s in result.sections], ensure_ascii=False
        )
    await db.commit()
    await db.refresh(contract)
    return contract


async def list_by_user(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    size: int = 20,
    is_admin: bool = False,
) -> list[Contract]:
    """列表查询：普通用户只看自己的，管理员看全部"""
    stmt = select(Contract)
    if not is_admin:
        stmt = stmt.where(Contract.uploader_id == user_id)
    stmt = stmt.order_by(Contract.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, contract_id: int) -> Optional[Contract]:
    result = await db.execute(
        select(Contract).where(Contract.id == contract_id)
    )
    return result.scalar_one_or_none()


async def delete_contract(
    db: AsyncSession,
    contract: Contract,
) -> None:
    """删除合同：同时删本地文件"""
    try:
        if contract.file_path and os.path.exists(contract.file_path):
            os.remove(contract.file_path)
    except OSError:
        pass  # 文件不存在就忽略

    await db.delete(contract)
    await db.commit()

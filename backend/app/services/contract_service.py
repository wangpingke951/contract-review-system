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
from sqlalchemy import select, func

from app.config import get_settings
from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.models.contract import Contract, ContractStatus
from app.parsers.factory import get_parser, supported_extensions

settings = get_settings()

# 解析内容少于该字数视为无效合同（PRD 4.3 异常处理：解析内容过少应阻断审查）
MIN_CONTRACT_CHARS = 200

# —— 文件扩展名 → file_type 映射 ——
_TYPE_MAP = {
    "pdf": "pdf",
    "docx": "docx",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
}


async def _save_contract_file(file: UploadFile, uploader_id: int) -> tuple[str, str, str]:
    """校验（扩展名 / 大小 / 魔数）并落盘，返回 (filename, file_path, ext)"""
    filename = file.filename or "unnamed"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = supported_extensions()
    if ext not in allowed:
        raise ValidationError(f"不支持的文件类型 .{ext}，允许: {sorted(allowed)}")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"文件超过 {settings.MAX_UPLOAD_SIZE_MB}MB 上限")

    upload_dir = os.path.join(settings.UPLOAD_DIR, str(uploader_id))
    os.makedirs(upload_dir, exist_ok=True)
    safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(filename)}"
    file_path = os.path.join(upload_dir, safe_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    from app.core import file_guard
    try:
        file_guard.verify(file_path, ext)
    except ValidationError:
        _remove_file(file_path)
        raise
    return filename, file_path, ext


async def _apply_parse(contract: Contract, file_path: str) -> None:
    """解析文件并把结果写进 contract 对象（不 commit）"""
    parser = get_parser(contract.filename)
    result = await parser.parse(file_path)

    error = _judge_parse_result(result)
    if error:
        contract.status = ContractStatus.PARSING_FAILED
        contract.parsed_content = ""
        contract.parsed_sections = None
        contract.parse_error = error
    else:
        contract.status = ContractStatus.PARSED
        contract.parsed_content = result.raw_text
        contract.parsed_sections = json.dumps(
            [s.__dict__ for s in result.sections], ensure_ascii=False
        )
        contract.parse_error = None


def _remove_file(path: str | None) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


async def upload_and_parse(
    db: AsyncSession,
    file: UploadFile,
    uploader_id: int,
    base: Optional[Contract] = None,
) -> Contract:
    """
    上传 + 解析（同步执行）

    流程：校验并落盘 → 建记录 → 解析 → 判定结果 → 落库
    解析类失败**不抛异常**，而是落库并随正常响应返回（status=parsing_failed + parse_error），
    这样批量上传时单个文件失败不会中断整批，前端也能逐条展示原因。
    """
    filename, file_path, ext = await _save_contract_file(file, uploader_id)

    contract = Contract(
        filename=filename,
        file_type=_TYPE_MAP.get(ext, ext),
        file_path=file_path,
        status=ContractStatus.PARSING,
        uploader_id=uploader_id,
        version=(base.version + 1) if base else 1,
        root_contract_id=((base.root_contract_id or base.id) if base else None),
        parent_contract_id=(base.id if base else None),
    )
    db.add(contract)
    await db.flush()  # 拿到 contract.id

    await _apply_parse(contract, file_path)

    await db.commit()
    await db.refresh(contract)
    return contract


async def reparse(
    db: AsyncSession,
    contract_id: int,
    user_id: int,
    is_admin: bool = False,
) -> Contract:
    """
    原地重新解析已保存的原始文件。

    适用场景：之前因为 OCR / 多模态模型未配置、解析器临时异常导致失败，
    配置修好后无需重新上传，直接重试即可。
    """
    from app.core.exceptions import PermissionError

    contract = await get_by_id(db, contract_id)
    if not contract:
        raise NotFoundError("合同不存在")
    if not is_admin and contract.uploader_id != user_id:
        raise PermissionError("无权重新解析此合同")
    if not contract.file_path or not os.path.exists(contract.file_path):
        raise ValidationError("原始文件已不存在，请重新上传该合同")
    if contract.status == ContractStatus.REVIEWING:
        raise ValidationError("该合同正在审查中，请稍后再试")

    await _apply_parse(contract, contract.file_path)
    await db.commit()
    await db.refresh(contract)
    return contract


async def replace_file(
    db: AsyncSession,
    contract_id: int,
    file: UploadFile,
    user_id: int,
    is_admin: bool = False,
) -> Contract:
    """
    用新文件替换该合同的原始文件并重新解析（解析失败后重传）。

    与「上传新版本」的区别：不新增记录、版本号不变，列表里不会多出一条。
    """
    from app.core.exceptions import PermissionError

    contract = await get_by_id(db, contract_id)
    if not contract:
        raise NotFoundError("合同不存在")
    if not is_admin and contract.uploader_id != user_id:
        raise PermissionError("无权替换此合同的文件")
    if contract.status == ContractStatus.REVIEWING:
        raise ValidationError("该合同正在审查中，请稍后再试")

    filename, file_path, ext = await _save_contract_file(file, contract.uploader_id)
    old_path = contract.file_path

    contract.filename = filename
    contract.file_path = file_path
    contract.file_type = _TYPE_MAP.get(ext, ext)
    await _apply_parse(contract, file_path)

    await db.commit()
    _remove_file(old_path)
    await db.refresh(contract)
    return contract


async def upload_new_version(
    db: AsyncSession,
    base_contract_id: int,
    file: UploadFile,
    uploader_id: int,
    is_admin: bool = False,
) -> Contract:
    """上传同一份合同的新版本（保留旧版本，供比对与问题闭环）"""
    base = await get_by_id(db, base_contract_id)
    if not base:
        raise NotFoundError("基准合同不存在")
    if not is_admin and base.uploader_id != uploader_id:
        from app.core.exceptions import PermissionError
        raise PermissionError("无权为该合同上传新版本")

    # 版本号 = 同族最大版本 + 1（避免删掉中间版本后编号重复）
    root_id = base.root_contract_id or base.id
    max_version = (await db.execute(
        select(func.max(Contract.version)).where(
            (Contract.id == root_id)
            | (Contract.root_contract_id == root_id)
            | (Contract.parent_contract_id == root_id)
        )
    )).scalar() or base.version

    new_contract = await upload_and_parse(db, file, uploader_id, base=base)
    if new_contract.version <= max_version:
        new_contract.version = max_version + 1
        await db.commit()
        await db.refresh(new_contract)
    return new_contract


def _judge_parse_result(result) -> str | None:
    """判定解析结果是否可用；返回 None 表示通过，否则返回面向用户的原因"""
    if result.parse_errors:
        return "；".join(result.parse_errors)

    if result.word_count < MIN_CONTRACT_CHARS:
        return (
            f"解析内容过短（仅提取到 {result.word_count} 字），"
            f"请确认上传的是否为完整合同文件"
        )

    # PRD 明确排除英文合同：中文占比过低时阻断
    if result.language != "zh-CN" and result.word_count > 50:
        return "当前版本仅支持中文合同，检测到文本中中文字符占比过低，请上传中文合同"

    return None


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


async def count_by_user(
    db: AsyncSession,
    user_id: int,
    is_admin: bool = False,
) -> int:
    """与 list_by_user 同条件的总数（分页器用）"""
    from sqlalchemy import func

    stmt = select(func.count(Contract.id))
    if not is_admin:
        stmt = stmt.where(Contract.uploader_id == user_id)
    return (await db.execute(stmt)).scalar() or 0


async def count_follow_ups(db: AsyncSession, contract_ids: list[int]) -> dict[int, int]:
    """
    批量统计每份合同的「提问轮次」（PRD 4.4：历史列表显示「有 N 条追问」）

    统计口径：该合同审查报告对应会话中 role=user 的消息条数。
    一次聚合查询，避免列表 N+1。
    """
    if not contract_ids:
        return {}
    from sqlalchemy import func
    from app.models.review import Review
    from app.models.conversation import Conversation, Message, ConversationRole

    stmt = (
        select(Review.contract_id, func.count(Message.id))
        .join(Conversation, Conversation.review_id == Review.id)
        .join(Message, Message.conversation_id == Conversation.id)
        .where(
            Review.contract_id.in_(contract_ids),
            Message.role == ConversationRole.USER,
        )
        .group_by(Review.contract_id)
    )
    rows = (await db.execute(stmt)).all()
    return {contract_id: count for contract_id, count in rows}


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

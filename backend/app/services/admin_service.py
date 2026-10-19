"""
app/services/admin_service.py — 管理后台业务逻辑

知识库：
- upload_knowledge: 解析 → 切块 → 向量化 → ChromaDB upsert → knowledge_docs 落库
- replace_knowledge: 原位替换（旧版本写入 knowledge_doc_versions，向量与文件同步替换）
- delete_knowledge: ChromaDB 按来源删除 + DB 记录删除（不可恢复）
- list_versions: 历史版本列表
风险类别：
- list / add / delete（至少保留 1 个；删除不影响历史报告的类别快照）
"""
from __future__ import annotations

import os
from datetime import datetime

from fastapi import UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.category import (
    KnowledgeDoc,
    KnowledgeDocVersion,
    KnowledgeCategory,
    KnowledgeStatus,
    RiskCategory,
)
from app.parsers.base import detect_chinese_ratio
from app.parsers.factory import get_parser, supported_extensions
from app.rag.chunker import chunk_knowledge_text
from app.rag.embedding import get_embedding
from app.rag import vectorstore

settings = get_settings()

# PRD 4.5：知识文档支持 DOCX / PDF / TXT（md 作为纯文本一并支持）
PLAIN_TEXT_EXTS = {"txt", "md"}


def knowledge_extensions() -> set[str]:
    """知识文档允许的扩展名（合同解析器 + 纯文本）"""
    return supported_extensions() | PLAIN_TEXT_EXTS


def _read_plain_text(path: str) -> str:
    """TXT 编码兜底：Windows 下 TXT 常见 UTF-8 / GBK，逐个尝试"""
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


async def _extract_text(filename: str, file_path: str) -> str:
    """按扩展名抽取纯文本；失败抛 ValidationError（面向用户的文案）"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in PLAIN_TEXT_EXTS:
        text = _read_plain_text(file_path)
        if not text.strip():
            raise ValidationError("文本文件内容为空")
        if detect_chinese_ratio(text) < 0.2 and len(text) > 50:
            raise ValidationError("当前版本仅支持中文知识文档")
        return text

    parser = get_parser(filename)
    parsed = await parser.parse(file_path)
    if parsed.parse_errors:
        raise ValidationError("；".join(parsed.parse_errors))
    if not parsed.raw_text.strip():
        raise ValidationError("文档解析结果为空，无法入库")
    if parsed.language != "zh-CN" and parsed.word_count > 50:
        raise ValidationError("当前版本仅支持中文知识文档")
    return parsed.raw_text


async def _save_upload(file: UploadFile) -> tuple[str, str]:
    """校验 + 落盘，返回 (filename, file_path)"""
    filename = file.filename or "unnamed"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = knowledge_extensions()
    if ext not in allowed:
        raise ValidationError(f"不支持的文件类型 .{ext}，允许: {sorted(allowed)}")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"文件超过 {settings.MAX_UPLOAD_SIZE_MB}MB 上限")

    kb_dir = os.path.join(settings.UPLOAD_DIR, "knowledge")
    os.makedirs(kb_dir, exist_ok=True)
    safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(filename)}"
    file_path = os.path.join(kb_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    # 真实类型校验（魔数），防止改扩展名绕过
    from app.core import file_guard
    try:
        file_guard.verify(file_path, ext)
    except ValidationError:
        _remove_file(file_path)
        raise

    return filename, file_path


async def _chunk_and_index(filename: str, text: str, doc_id: int, category: KnowledgeCategory) -> int:
    """切块 + 向量化 + 写向量库，返回切块数"""
    chunks = chunk_knowledge_text(
        text, source_doc_id=doc_id,
        source_filename=filename, category=category.value,
    )
    if not chunks:
        raise ValidationError("切块结果为空")

    embedding = get_embedding()
    vectors = await embedding.embed_batch([c.text for c in chunks])
    vectorstore.upsert_chunks(
        chunks=[c.text for c in chunks],
        metadatas=[c.metadata for c in chunks],
        embeddings=vectors,
    )
    return len(chunks)


def _remove_file(path: str | None) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# —————————— 知识库 ——————————
async def upload_knowledge(
    db: AsyncSession,
    file: UploadFile,
    category: KnowledgeCategory,
    admin_id: int,
) -> KnowledgeDoc:
    filename, file_path = await _save_upload(file)

    doc = KnowledgeDoc(
        filename=filename,
        file_path=file_path,
        category=category,
        status=KnowledgeStatus.CHUNKING,
        uploader_id=admin_id,
    )
    db.add(doc)
    await db.flush()

    try:
        text = await _extract_text(filename, file_path)
        doc.chunk_count = await _chunk_and_index(filename, text, doc.id, category)
        doc.status = KnowledgeStatus.ENABLED
    except ValidationError:
        doc.status = KnowledgeStatus.FAILED
        await db.commit()
        raise
    except Exception as e:
        doc.status = KnowledgeStatus.FAILED
        await db.commit()
        raise ValidationError(f"知识文档处理失败: {e}")

    await db.commit()
    await db.refresh(doc)
    return doc


async def replace_knowledge(
    db: AsyncSession,
    doc_id: int,
    file: UploadFile,
    category: KnowledgeCategory,
    admin_id: int,
) -> KnowledgeDoc:
    """
    原位替换知识文档内容（PRD P1：知识库编辑）

    - 旧版本信息快照写入 knowledge_doc_versions
    - 旧向量按 source_doc_id 清除，旧文件删除
    - 解析/切块/向量化失败时，文档标记 failed，旧内容已被清除（与删除再上传等价）
    """
    doc = (await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
    )).scalar_one_or_none()
    if not doc:
        raise NotFoundError("知识文档不存在")

    filename, file_path = await _save_upload(file)

    # 旧版本快照
    db.add(KnowledgeDocVersion(
        doc_id=doc.id,
        filename=doc.filename,
        category=doc.category,
        chunk_count=doc.chunk_count,
        replaced_by=admin_id,
    ))

    # 清旧向量与旧文件
    vectorstore.delete_by_source(doc.id)
    old_path = doc.file_path

    doc.filename = filename
    doc.file_path = file_path
    doc.category = category
    doc.status = KnowledgeStatus.CHUNKING

    try:
        text = await _extract_text(filename, file_path)
        doc.chunk_count = await _chunk_and_index(filename, text, doc.id, category)
        doc.status = KnowledgeStatus.ENABLED
    except ValidationError:
        doc.status = KnowledgeStatus.FAILED
        await db.commit()
        raise
    except Exception as e:
        doc.status = KnowledgeStatus.FAILED
        await db.commit()
        raise ValidationError(f"知识文档替换失败: {e}")

    _remove_file(old_path)
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_knowledge(db: AsyncSession) -> list[KnowledgeDoc]:
    result = await db.execute(select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc()))
    return list(result.scalars().all())


async def list_versions(db: AsyncSession, doc_id: int) -> list[KnowledgeDocVersion]:
    doc = (await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
    )).scalar_one_or_none()
    if not doc:
        raise NotFoundError("知识文档不存在")
    result = await db.execute(
        select(KnowledgeDocVersion)
        .where(KnowledgeDocVersion.doc_id == doc_id)
        .order_by(KnowledgeDocVersion.replaced_at.desc())
    )
    return list(result.scalars().all())


async def delete_knowledge(db: AsyncSession, doc_id: int) -> None:
    doc = (await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
    )).scalar_one_or_none()
    if not doc:
        raise NotFoundError("知识文档不存在")

    # ChromaDB 按来源删除全部 chunks
    vectorstore.delete_by_source(doc.id)
    _remove_file(doc.file_path)

    await db.delete(doc)
    await db.commit()


# —————————— 风险类别 ——————————
async def list_categories(db: AsyncSession) -> list[RiskCategory]:
    result = await db.execute(select(RiskCategory).order_by(RiskCategory.id))
    return list(result.scalars().all())


async def add_category(db: AsyncSession, name: str, admin_id: int) -> RiskCategory:
    name = name.strip()
    if not name:
        raise ValidationError("类别名不能为空")
    if len(name) > 64:
        raise ValidationError("类别名不能超过 64 字")
    exists = (await db.execute(
        select(func.count(RiskCategory.id)).where(RiskCategory.name == name)
    )).scalar()
    if exists:
        raise ValidationError(f"类别「{name}」已存在")
    cat = RiskCategory(name=name, created_by=admin_id)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


async def delete_category(db: AsyncSession, cat_id: int) -> None:
    cat = (await db.execute(
        select(RiskCategory).where(RiskCategory.id == cat_id)
    )).scalar_one_or_none()
    if not cat:
        raise NotFoundError("风险类别不存在")
    total = (await db.execute(select(func.count(RiskCategory.id)))).scalar()
    if total <= 1:
        raise ValidationError("至少需要保留 1 个风险类别，无法删除")
    # 历史报告的 category_id 为 SET NULL，category_name 快照保留 → 无需额外处理
    await db.delete(cat)
    await db.commit()

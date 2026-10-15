"""
app/services/admin_service.py — 管理后台业务逻辑

知识库：
- upload_knowledge: 解析 → 切块 → 向量化 → ChromaDB upsert → knowledge_docs 落库
- delete_knowledge: ChromaDB 按来源删除 + DB 记录删除（不可恢复，PRD v1.1 决策）
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
from app.models.category import KnowledgeDoc, KnowledgeCategory, KnowledgeStatus, RiskCategory
from app.parsers.factory import get_parser, supported_extensions
from app.rag.chunker import chunk_knowledge_text
from app.rag.embedding import get_embedding
from app.rag import vectorstore

settings = get_settings()


# —————————— 知识库 ——————————
async def upload_knowledge(
    db: AsyncSession,
    file: UploadFile,
    category: KnowledgeCategory,
    admin_id: int,
) -> KnowledgeDoc:
    filename = file.filename or "unnamed"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in supported_extensions():
        raise ValidationError(f"不支持的文件类型 .{ext}，允许: {sorted(supported_extensions())}")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"文件超过 {settings.MAX_UPLOAD_SIZE_MB}MB 上限")

    # 保存文件
    kb_dir = os.path.join(settings.UPLOAD_DIR, "knowledge")
    os.makedirs(kb_dir, exist_ok=True)
    safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(filename)}"
    file_path = os.path.join(kb_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    # 落库记录（chunking 状态）
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
        # 解析
        parser = get_parser(filename)
        parsed = await parser.parse(file_path)
        if not parsed.raw_text.strip():
            raise ValidationError("文档解析结果为空，无法入库")
        if parsed.language != "zh-CN" and parsed.word_count > 50:
            raise ValidationError("当前版本仅支持中文知识文档")

        # 切块
        chunks = chunk_knowledge_text(
            parsed.raw_text, source_doc_id=doc.id,
            source_filename=filename, category=category.value,
        )
        if not chunks:
            raise ValidationError("切块结果为空")

        # 向量化（在线 API）+ 入库
        embedding = get_embedding()
        vectors = await embedding.embed_batch([c.text for c in chunks])
        vectorstore.upsert_chunks(
            chunks=[c.text for c in chunks],
            metadatas=[c.metadata for c in chunks],
            embeddings=vectors,
        )

        doc.status = KnowledgeStatus.ENABLED
        doc.chunk_count = len(chunks)
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


async def list_knowledge(db: AsyncSession) -> list[KnowledgeDoc]:
    result = await db.execute(select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc()))
    return list(result.scalars().all())


async def delete_knowledge(db: AsyncSession, doc_id: int) -> None:
    doc = (await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))).scalar_one_or_none()
    if not doc:
        raise NotFoundError("知识文档不存在")

    # ChromaDB 按来源删除全部 chunks
    vectorstore.delete_by_source(doc.id)

    # 删除本地文件
    try:
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except OSError:
        pass

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
    cat = (await db.execute(select(RiskCategory).where(RiskCategory.id == cat_id))).scalar_one_or_none()
    if not cat:
        raise NotFoundError("风险类别不存在")
    total = (await db.execute(select(func.count(RiskCategory.id)))).scalar()
    if total <= 1:
        raise ValidationError("至少需要保留 1 个风险类别，无法删除")
    # 历史报告的 category_id 为 SET NULL，category_name 快照保留 → 无需额外处理
    await db.delete(cat)
    await db.commit()

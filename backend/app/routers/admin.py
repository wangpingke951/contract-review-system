"""
app/routers/admin.py — 管理后台 API（全部 admin-only）

知识库：
POST   /api/admin/knowledge/upload      上传知识文档（解析→切块→向量化→入库）
GET    /api/admin/knowledge             知识文档列表
PUT    /api/admin/knowledge/{id}        原位替换文档内容（旧版本入历史）
GET    /api/admin/knowledge/{id}/versions 历史版本列表
DELETE /api/admin/knowledge/{id}        删除（ChromaDB 同步清除）
风险类别：
GET    /api/admin/categories            列表
POST   /api/admin/categories            新增
DELETE /api/admin/categories/{id}       删除（至少保留 1 个）
审计：
GET    /api/admin/audit-logs            操作日志（分页 + 按动作筛选）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_admin, TokenPayload
from app.core.exceptions import ValidationError
from app.models.audit import (
    ACTION_KNOWLEDGE_DELETE,
    ACTION_KNOWLEDGE_REPLACE,
    ACTION_KNOWLEDGE_UPLOAD,
)
from app.models.category import KnowledgeCategory
from app.services import admin_service, audit_service, usage_service
from app.schemas.admin import (
    KnowledgeDocOut,
    KnowledgeVersionOut,
    KnowledgeBatchUploadResponse,
    KnowledgeProgressOut,
    CategoryOut,
    CategoryCreate,
    AuditLogOut,
    AuditLogListResponse,
)

router = APIRouter()

# 单次批量上传的文件数上限（防止一次拖 100 个文件把队列堵死）
MAX_BATCH_FILES = 20


def _doc_out(d) -> KnowledgeDocOut:
    # 已入库的一律视为 100%（历史数据可能没写 progress）
    progress = 100 if d.status.value == "enabled" else (d.progress or 0)
    return KnowledgeDocOut(
        id=d.id,
        filename=d.filename,
        category=d.category.value,
        status=d.status.value,
        chunk_count=d.chunk_count,
        created_at=d.created_at,
        progress=progress,
        processed_chunks=d.processed_chunks or 0,
        total_chunks=d.total_chunks or 0,
        error_message=d.error_message,
    )


def _parse_category(raw: str) -> KnowledgeCategory:
    """
    category 入参统一按小写值解析（guide / template / case / law）。
    历史报错文案曾列出枚举成员名导致误导，这里对大小写宽容。
    """
    try:
        return KnowledgeCategory((raw or "").strip().lower())
    except ValueError:
        valid = [c.value for c in KnowledgeCategory]
        raise ValidationError(f"category 必须是 {valid} 之一")


# —————————— 知识库 ——————————
@router.post("/knowledge/upload", response_model=KnowledgeDocOut)
async def upload_knowledge(
    file: UploadFile = File(...),
    category: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    cat = _parse_category(category)
    doc = await admin_service.upload_knowledge(db, file, cat, current.user_id)
    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_KNOWLEDGE_UPLOAD,
        target_type="knowledge_doc",
        target_id=doc.id,
        detail=f"{doc.filename}（{doc.category.value}，后台入库中）",
        commit=True,
    )
    return _doc_out(doc)


@router.post("/knowledge/upload-batch", response_model=KnowledgeBatchUploadResponse)
async def upload_knowledge_batch(
    files: list[UploadFile] = File(...),
    category: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    """
    批量上传：每个文件单独建记录，后台串行入库。

    单个文件校验失败（类型/大小/魔数）只记入 rejected，不影响其它文件。
    """
    if len(files) > MAX_BATCH_FILES:
        raise ValidationError(f"一次最多上传 {MAX_BATCH_FILES} 个文件，当前 {len(files)} 个")

    cat = _parse_category(category)
    uploaded = []
    rejected = []

    for f in files:
        try:
            doc = await admin_service.upload_knowledge(db, f, cat, current.user_id)
            uploaded.append(_doc_out(doc))
        except ValidationError as e:
            rejected.append({"filename": f.filename or "unnamed", "reason": str(e)})

    if uploaded:
        await audit_service.record(
            db,
            actor_id=current.user_id,
            actor_name=current.username,
            action=ACTION_KNOWLEDGE_UPLOAD,
            target_type="knowledge_doc",
            target_id=uploaded[0].id,
            detail=f"批量上传 {len(uploaded)} 个文档（{cat.value}）",
            commit=True,
        )

    return KnowledgeBatchUploadResponse(uploaded=uploaded, rejected=rejected)


@router.get("/knowledge/{doc_id}/progress", response_model=KnowledgeProgressOut)
async def knowledge_progress(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    """前端轮询入库进度；status 为 enabled / failed 时即可停止轮询"""
    d = await admin_service.get_knowledge_progress(db, doc_id)
    return KnowledgeProgressOut(
        id=d.id,
        status=d.status.value,
        progress=d.progress or 0,
        processed_chunks=d.processed_chunks or 0,
        total_chunks=d.total_chunks or 0,
        chunk_count=d.chunk_count,
        error_message=d.error_message,
    )


@router.post("/knowledge/{doc_id}/retry", response_model=KnowledgeDocOut)
async def retry_knowledge(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    """失败文档原地重试入库（复用已保存的原文件，无需重新上传）"""
    doc = await admin_service.retry_ingest(db, doc_id)
    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_KNOWLEDGE_UPLOAD,
        target_type="knowledge_doc",
        target_id=doc.id,
        detail=f"重试入库：{doc.filename}",
        commit=True,
    )
    return _doc_out(doc)


@router.put("/knowledge/{doc_id}", response_model=KnowledgeDocOut)
async def replace_knowledge(
    doc_id: int,
    file: UploadFile = File(...),
    category: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    cat = _parse_category(category)
    doc = await admin_service.replace_knowledge(db, doc_id, file, cat, current.user_id)
    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_KNOWLEDGE_REPLACE,
        target_type="knowledge_doc",
        target_id=doc.id,
        detail=f"{doc.filename}（{doc.category.value}，替换后后台入库中）",
        commit=True,
    )
    return _doc_out(doc)


@router.get("/knowledge/{doc_id}/versions", response_model=list[KnowledgeVersionOut])
async def list_versions(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    versions = await admin_service.list_versions(db, doc_id)
    return [
        KnowledgeVersionOut(
            id=v.id, filename=v.filename, category=v.category.value,
            chunk_count=v.chunk_count, replaced_at=v.replaced_at,
        )
        for v in versions
    ]


@router.get("/knowledge", response_model=list[KnowledgeDocOut])
async def list_knowledge(
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    docs = await admin_service.list_knowledge(db)
    return [_doc_out(d) for d in docs]


@router.delete("/knowledge/{doc_id}")
async def delete_knowledge(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    await admin_service.delete_knowledge(db, doc_id)
    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_KNOWLEDGE_DELETE,
        target_type="knowledge_doc",
        target_id=doc_id,
        detail="删除知识文档及其向量",
        commit=True,
    )
    return {"code": 0, "message": "删除成功（向量库已同步清除）", "data": None}


# —————————— 风险类别 ——————————
@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    cats = await admin_service.list_categories(db)
    return [CategoryOut(id=c.id, name=c.name, created_at=c.created_at) for c in cats]


@router.post("/categories", response_model=CategoryOut)
async def add_category(
    body: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    cat = await admin_service.add_category(db, body.name, current.user_id)
    return CategoryOut(id=cat.id, name=cat.name, created_at=cat.created_at)


@router.delete("/categories/{cat_id}")
async def delete_category(
    cat_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    await admin_service.delete_category(db, cat_id)
    return {"code": 0, "message": "删除成功", "data": None}


@router.get("/usage-stats")
async def usage_stats(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    """LLM 调用用量统计（近 N 天）"""
    return await usage_service.stats(db, days=days)


# —————————— 审计日志 ——————————
@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    action: str | None = Query(None, description="按动作筛选，留空为全部"),
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    items, total = await audit_service.list_logs(db, page=page, size=size, action=action)
    return AuditLogListResponse(
        items=[AuditLogOut(**it) for it in items],
        total=total,
    )

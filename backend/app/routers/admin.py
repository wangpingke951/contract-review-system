"""
app/routers/admin.py — 管理后台 API（全部 admin-only）

知识库：
POST   /api/admin/knowledge/upload   上传知识文档（解析→切块→向量化→入库）
GET    /api/admin/knowledge          知识文档列表
DELETE /api/admin/knowledge/{id}     删除（ChromaDB 同步清除）
风险类别：
GET    /api/admin/categories         列表
POST   /api/admin/categories         新增
DELETE /api/admin/categories/{id}    删除（至少保留 1 个）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_admin, TokenPayload
from app.models.category import KnowledgeCategory
from app.services import admin_service
from app.schemas.admin import KnowledgeDocOut, CategoryOut, CategoryCreate

router = APIRouter()


# —————————— 知识库 ——————————
@router.post("/knowledge/upload", response_model=KnowledgeDocOut)
async def upload_knowledge(
    file: UploadFile = File(...),
    category: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    try:
        cat = KnowledgeCategory(category)
    except ValueError:
        from app.core.exceptions import ValidationError
        raise ValidationError(f"category 必须是 {list(KnowledgeCategory.__members__)} 之一")

    doc = await admin_service.upload_knowledge(db, file, cat, current.user_id)
    return KnowledgeDocOut(
        id=doc.id, filename=doc.filename, category=doc.category.value,
        status=doc.status.value, chunk_count=doc.chunk_count, created_at=doc.created_at,
    )


@router.get("/knowledge", response_model=list[KnowledgeDocOut])
async def list_knowledge(
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    docs = await admin_service.list_knowledge(db)
    return [KnowledgeDocOut(
        id=d.id, filename=d.filename, category=d.category.value,
        status=d.status.value, chunk_count=d.chunk_count, created_at=d.created_at,
    ) for d in docs]


@router.delete("/knowledge/{doc_id}")
async def delete_knowledge(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(get_current_admin),
):
    await admin_service.delete_knowledge(db, doc_id)
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

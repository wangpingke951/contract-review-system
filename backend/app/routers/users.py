"""
app/routers/users.py — 用户与权限管理（后台）

接口：
GET    /api/admin/users                 用户列表（含权限、状态、创建时间）
GET    /api/admin/users/permissions     可授予的权限点目录
PUT    /api/admin/users/{id}/permissions 授予/回收权限
PUT    /api/admin/users/{id}/status      启用/禁用账号
PUT    /api/admin/users/{id}/password    重置密码

设计约束：
- 全部接口需要 user:manage 权限（管理员天然具备，也可单独授予某人）
- 不能操作管理员账号：改权限、禁用、重置密码一律拒绝，
  避免把系统里唯一的 admin 锁死
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, TokenPayload
from app.core.exceptions import NotFoundError, ValidationError
from app.core.permissions import (
    PERMISSIONS,
    dump_permissions,
    effective_permissions,
    permission_label,
)
from app.core.security import UserRole, hash_password
from app.models.audit import ACTION_USER_PERMISSION, ACTION_USER_STATUS
from app.models.user import User
from app.schemas.user import (
    PermissionItem,
    UserOut,
    UserPermissionUpdate,
    UserPasswordReset,
    UserStatusUpdate,
)
from app.services import audit_service

router = APIRouter()


def _user_out(u: User) -> UserOut:
    perms = effective_permissions(u.role, u.permissions)
    return UserOut(
        id=u.id,
        username=u.username,
        role=u.role.value,
        permissions=sorted(perms),
        is_active=u.is_active,
        created_at=u.created_at,
    )


async def _get_target(db: AsyncSession, user_id: int) -> User:
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        raise NotFoundError("用户不存在")
    return u


def _ensure_not_admin(u: User, action: str) -> None:
    if u.role == UserRole.ADMIN:
        raise ValidationError(f"不能对管理员账号执行「{action}」")


@router.get("/permissions", response_model=list[PermissionItem])
async def list_permissions(
    current: TokenPayload = Depends(require_permission("user:manage")),
):
    """可授予的权限点目录（前端渲染勾选框用）"""
    return [PermissionItem(**p) for p in PERMISSIONS]


@router.get("", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(require_permission("user:manage")),
):
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    return [_user_out(u) for u in users]


@router.put("/{user_id}/permissions", response_model=UserOut)
async def update_permissions(
    user_id: int,
    body: UserPermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(require_permission("user:manage")),
):
    """全量覆盖该用户的权限点（前端提交勾选后的完整列表）"""
    u = await _get_target(db, user_id)
    _ensure_not_admin(u, "修改权限")

    try:
        before = effective_permissions(u.role, u.permissions)
        u.permissions = dump_permissions(body.permissions)
        after = effective_permissions(u.role, u.permissions)
    except ValueError as e:
        raise ValidationError(str(e))

    await db.commit()
    await db.refresh(u)

    added = sorted(after - before)
    removed = sorted(before - after)
    parts = []
    if added:
        parts.append("新增 " + "、".join(permission_label(k) for k in added))
    if removed:
        parts.append("移除 " + "、".join(permission_label(k) for k in removed))
    detail = f"{u.username}：" + ("；".join(parts) if parts else "无变化")

    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_USER_PERMISSION,
        target_type="user",
        target_id=u.id,
        detail=detail,
        commit=True,
    )
    return _user_out(u)


@router.put("/{user_id}/status", response_model=UserOut)
async def update_status(
    user_id: int,
    body: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(require_permission("user:manage")),
):
    """启用 / 禁用账号。禁用后已签发的 token 也会立即失效（每次请求查库）。"""
    u = await _get_target(db, user_id)
    _ensure_not_admin(u, "启用/禁用")
    if u.id == current.user_id:
        raise ValidationError("不能禁用自己的账号")

    u.is_active = body.is_active
    await db.commit()
    await db.refresh(u)

    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_USER_STATUS,
        target_type="user",
        target_id=u.id,
        detail=f"{u.username}：{'启用' if body.is_active else '禁用'}",
        commit=True,
    )
    return _user_out(u)


@router.put("/{user_id}/password", response_model=dict)
async def reset_password(
    user_id: int,
    body: UserPasswordReset,
    db: AsyncSession = Depends(get_db),
    current: TokenPayload = Depends(require_permission("user:manage")),
):
    """管理员重置密码（账号被锁或忘记密码时的兜底手段）"""
    u = await _get_target(db, user_id)
    if not (6 <= len(body.new_password) <= 64):
        raise ValidationError("密码长度需为 6–64 位")

    u.hashed_password = hash_password(body.new_password)
    await db.commit()

    await audit_service.record(
        db,
        actor_id=current.user_id,
        actor_name=current.username,
        action=ACTION_USER_PERMISSION,
        target_type="user",
        target_id=u.id,
        detail=f"{u.username}：重置密码",
        commit=True,
    )
    return {"code": 0, "data": {"user_id": u.id}, "message": "密码已重置"}

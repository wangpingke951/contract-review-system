"""
app/core/dependencies.py — FastAPI Depends 依赖注入

关键设计：
- get_current_user: 解析 JWT 后**回查数据库**，确认账号仍存在且未被禁用，
  并把最新的权限点填进 TokenPayload。这样管理员改权限/禁用账号能立刻生效，
  不用等 token 过期。
- require_permission(*keys): 权限点校验工厂，供各路由按模块引用
- get_current_admin: 仅校验 role=admin，用于不可授予的能力（如模型配置）
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from jose import JWTError
from sqlalchemy import select

from app.core.database import get_db
from app.core.permissions import effective_permissions
from app.core.security import (
    TokenPayload,
    decode_access_token,
    UserRole,
)


def _extract_token(request: Request) -> Optional[str]:
    """从 Authorization header 提取 Bearer token"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


async def get_current_user(
    request: Request,
    db=Depends(get_db),
) -> TokenPayload:
    """
    获取当前登录用户，失败返回 401。

    注意：这里会查一次 users 表（主键查询，代价可忽略），
    换来的是「权限变更即时生效 + 禁用立即踢下线」。
    """
    from app.models.user import User

    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
        token_data = TokenPayload(payload)
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = (await db.execute(
        select(User).where(User.id == token_data.user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号不存在，请重新登录",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
        )

    # 以数据库为准：角色可能被调整，权限可能被授予或回收
    token_data.role = user.role
    token_data.username = user.username
    token_data.is_active = user.is_active
    token_data.permissions = effective_permissions(user.role, user.permissions)
    return token_data


async def get_current_admin(
    current_user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """管理员专属：仅校验 role=admin（不可通过授权获得）"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user


def require_permission(*keys: str):
    """
    权限点校验工厂（多个 key 之间是「或」的关系）。

        @router.get("/knowledge")
        async def list_knowledge(current = Depends(require_permission("knowledge:manage"))):
            ...

    管理员天然通过；普通用户需被授予其中任一权限点。
    """
    async def _checker(current: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if current.role == UserRole.ADMIN:
            return current
        if any(k in current.permissions for k in keys):
            return current
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"缺少权限：{' 或 '.join(keys)}",
        )

    return _checker

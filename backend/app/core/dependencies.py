"""
app/core/dependencies.py — FastAPI Depends 依赖注入

关键设计：
- get_current_user: 从 Authorization header 解析 JWT → 返回 User ORM 对象
- get_current_admin: 在 get_current_user 基础上加角色校验
- 数据库 session 通过 db: AsyncSession = Depends(get_db) 注入
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from jose import JWTError

from app.core.database import get_db
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
    db=Depends(get_db),   # noqa: F401 — 暂不查询 DB，Phase 2 后续会接入 User model
) -> TokenPayload:
    """
    获取当前登录用户的 TokenPayload
    失败（无 token / token 过期 / 篡改）返回 401
    """
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
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


async def get_current_admin(
    current_user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """管理员权限校验：在 get_current_user 基础上校验 role=admin"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user

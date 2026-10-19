"""
app/routers/auth.py — 真实认证路由（DB 查询 + JWT）

POST /api/auth/login         → 真实登录（查 users 表 + verify_password）
POST /api/auth/register      → 注册普通用户
GET  /api/auth/me            → 返回当前 JWT 解析后的用户信息
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import (
    UserRole,
    create_access_token,
    verify_password,
    hash_password,
    TokenPayload,
)
from app.models.audit import ACTION_AUTH_LOGIN
from app.models.user import User
from app.services import audit_service

settings = get_settings()

router = APIRouter()


# —— 请求/响应 schema ——
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    confirm_password: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户登录（真实 DB 查询）"""
    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )
    # PRD 5.3：管理员登录记审计
    if user.role == UserRole.ADMIN:
        await audit_service.record(
            db,
            actor_id=user.id,
            actor_name=user.username,
            action=ACTION_AUTH_LOGIN,
            target_type="user",
            target_id=user.id,
            detail="管理员登录",
            commit=True,
        )
    return TokenResponse(access_token=token, role=user.role.value)


@router.post("/register", response_model=dict)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    自助注册普通用户（不允许注册管理员）

    校验：用户名 3–32 位（字母/数字/下划线/中文）、密码 ≥6 位、两次输入一致、
    非保留用户名。注册成功直接签发 token，前端可免登录直接进入系统。
    """
    if not settings.ALLOW_REGISTER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员已关闭自助注册，请联系管理员开通账号",
        )

    username = (body.username or "").strip()
    password = body.password or ""

    if not (3 <= len(username) <= 32):
        raise HTTPException(status_code=400, detail="用户名长度需为 3–32 位")
    if not re.fullmatch(r"[A-Za-z0-9_\u4e00-\u9fa5]+", username):
        raise HTTPException(status_code=400, detail="用户名只能包含字母、数字、下划线或中文")
    if username.lower() in settings.reserved_usernames:
        raise HTTPException(status_code=400, detail="该用户名为系统保留，请换一个")

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    if len(password) > 64:
        raise HTTPException(status_code=400, detail="密码不能超过 64 位")
    if body.confirm_password is not None and body.confirm_password != password:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致")

    exists = (await db.execute(
        select(User).where(User.username == username)
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在，请换一个")

    user = User(
        username=username,
        hashed_password=hash_password(password),
        role=UserRole.USER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )
    return {
        "code": 0,
        "data": {
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value,
            "access_token": token,
            "token_type": "bearer",
        },
        "message": "注册成功",
    }


@router.get("/me", response_model=UserResponse)
async def get_me(current: TokenPayload = Depends(get_current_user)):
    """获取当前登录用户（需 JWT）"""
    return UserResponse(
        id=current.user_id,
        username=current.username,
        role=current.role.value,
    )

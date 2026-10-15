"""
app/routers/auth.py — 真实认证路由（DB 查询 + JWT）

POST /api/auth/login         → 真实登录（查 users 表 + verify_password）
POST /api/auth/register      → 注册普通用户
GET  /api/auth/me            → 返回当前 JWT 解析后的用户信息
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import (
    UserRole,
    create_access_token,
    verify_password,
    hash_password,
    TokenPayload,
)
from app.models.user import User

router = APIRouter()


# —— 请求/响应 schema ——
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


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
    return TokenResponse(access_token=token, role=user.role.value)


@router.post("/register", response_model=dict)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """注册普通用户（不允许注册 admin）"""
    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=UserRole.USER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"code": 0, "data": {"user_id": user.id}, "message": "注册成功"}


@router.get("/me", response_model=UserResponse)
async def get_me(current: TokenPayload = Depends(get_current_user)):
    """获取当前登录用户（需 JWT）"""
    return UserResponse(
        id=current.user_id,
        username=current.username,
        role=current.role.value,
    )

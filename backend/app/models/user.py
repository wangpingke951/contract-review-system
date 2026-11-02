"""User ORM — 普通用户 + 管理员共用"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, String, Integer, Column, Enum, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.security import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.USER,
    )
    # 授予普通用户的细粒度权限点（逗号分隔，见 app/core/permissions.py）。
    # 管理员不看这个字段 —— admin 恒拥有全部权限。
    permissions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 禁用后无法登录，已签发的 token 也会被拒绝（每次请求都会查库）
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        nullable=False,
    )

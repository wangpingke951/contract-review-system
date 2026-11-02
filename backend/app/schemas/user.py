"""app/schemas/user.py — 用户与权限管理相关模型"""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    permissions: List[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime


class PermissionItem(BaseModel):
    key: str
    label: str
    desc: str


class UserPermissionUpdate(BaseModel):
    # 全量覆盖，前端提交勾选后的完整权限列表
    permissions: List[str] = Field(default_factory=list)


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserPasswordReset(BaseModel):
    new_password: str

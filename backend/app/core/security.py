"""
app/core/security.py — JWT + 密码 hash + 角色 RBAC

关键设计：
- 使用 python-jose 做 JWT 编解码
- passlib[bcrypt] 做密码 hash
- 角色为枚举：user / admin
- 后端解析 JWT 时做角色校验
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from enum import Enum

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# —— 密码 hash 工具（bcrypt）——
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# —— 角色枚举 ——
class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


# —— 密码工具 ——
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# —— JWT 工具 ——
def create_access_token(
    user_id: int,
    username: str,
    role: UserRole,
    expires_minutes: Optional[int] = None,
) -> str:
    """生成 JWT access token"""
    expire_minutes = expires_minutes or settings.JWT_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": str(user_id),           # subject: 用户 ID
        "username": username,
        "role": role.value,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """解码 JWT，失败抛出 JWTError"""
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


class TokenPayload:
    """解析后的 token payload（结构化视图）"""
    def __init__(self, data: dict):
        self.user_id = int(data["sub"])
        self.username: str = data["username"]
        self.role: UserRole = UserRole(data["role"])

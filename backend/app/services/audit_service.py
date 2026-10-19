"""app/services/audit_service.py — 审计日志写入与查询"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User


async def record(
    db: AsyncSession,
    *,
    actor_id: Optional[int],
    actor_name: str,
    action: str,
    target_type: str = "",
    target_id: Optional[int] = None,
    detail: Optional[str] = None,
    commit: bool = False,
) -> AuditLog:
    """
    写一条审计日志。

    默认只 add 不 commit —— 跟随调用方的事务，避免主流程失败时日志先落库。
    独立场景（如登录）传 commit=True。
    """
    entry = AuditLog(
        actor_id=actor_id,
        actor_name=actor_name or "",
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    db.add(entry)
    if commit:
        await db.commit()
        await db.refresh(entry)
    return entry


async def list_logs(
    db: AsyncSession,
    page: int = 1,
    size: int = 50,
    action: Optional[str] = None,
) -> tuple[list[dict], int]:
    """分页查询审计日志，action 为空表示全部"""
    base = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))
    if action:
        base = base.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = base.order_by(desc(AuditLog.created_at)).offset((page - 1) * size).limit(size)
    rows = (await db.execute(stmt)).scalars().all()

    items = [
        {
            "id": r.id,
            "actor_id": r.actor_id,
            "actor_name": r.actor_name,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "detail": r.detail,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return items, total

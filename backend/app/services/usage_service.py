"""
app/services/usage_service.py — LLM 用量记录与统计

审查（非流式）能拿到准确 token；追问（流式）只记调用次数与耗时，
token 记为 0（OpenAI 流式协议需 stream_options.include_usage 才返回，未启用）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import LLMUsage


async def record(
    db: AsyncSession,
    *,
    user_id: int | None,
    scene: str,
    model: str = "",
    usage: dict | None = None,
    duration_ms: int = 0,
    success: bool = True,
) -> None:
    u = usage or {}
    prompt_tokens = int(u.get("prompt_tokens") or 0)
    completion_tokens = int(u.get("completion_tokens") or 0)
    total = int(u.get("total_tokens") or (prompt_tokens + completion_tokens))
    db.add(LLMUsage(
        user_id=user_id,
        scene=scene,
        model=model or "",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total,
        duration_ms=duration_ms,
        success=success,
    ))
    # 调用方负责 commit，避免打断主事务


async def stats(db: AsyncSession, days: int = 7) -> dict:
    """近 N 天用量聚合：按场景、按天"""
    since = datetime.now() - timedelta(days=max(days, 1))

    rows = (await db.execute(
        select(
            LLMUsage.scene,
            func.count(LLMUsage.id),
            func.coalesce(func.sum(LLMUsage.total_tokens), 0),
            func.coalesce(func.avg(LLMUsage.duration_ms), 0),
        )
        .where(LLMUsage.created_at >= since)
        .group_by(LLMUsage.scene)
    )).all()

    by_scene = [
        {
            "scene": scene,
            "calls": int(calls),
            "tokens": int(tokens),
            "avg_duration_ms": int(avg_ms or 0),
        }
        for scene, calls, tokens, avg_ms in rows
    ]

    daily = (await db.execute(
        select(
            func.date(LLMUsage.created_at),
            func.count(LLMUsage.id),
            func.coalesce(func.sum(LLMUsage.total_tokens), 0),
        )
        .where(LLMUsage.created_at >= since)
        .group_by(func.date(LLMUsage.created_at))
        .order_by(func.date(LLMUsage.created_at))
    )).all()

    total_calls = sum(s["calls"] for s in by_scene)
    total_tokens = sum(s["tokens"] for s in by_scene)

    return {
        "days": days,
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "by_scene": by_scene,
        "daily": [
            {"date": str(d), "calls": int(c), "tokens": int(t)}
            for d, c, t in daily
        ],
    }

"""
app/services/config_service.py — 运行期模型配置

优先级：数据库（管理员在页面上改的） > .env
- reload(db)   启动时与保存后调用，把生效配置刷进进程内存
- snapshot()   同步读取内存快照，供 LLM 工厂 / 视觉模型同步调用
- update(...)  写库并立刻 reload，无需重启服务
"""
from __future__ import annotations

import time
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ValidationError
from app.models.system import SystemSetting

settings = get_settings()

# 各供应商默认 base_url / 推荐模型（前端下拉用）
PROVIDERS = [
    {
        "id": "siliconflow",
        "name": "硅基流动 SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": ["Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-V3"],
        "vision_models": ["Qwen/Qwen2.5-VL-7B-Instruct"],
    },
    {
        "id": "doubao",
        "name": "字节豆包 Ark",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": ["doubao-pro-32k", "doubao-lite-32k"],
        "vision_models": ["doubao-vision-pro-32k"],
    },
    {
        "id": "qwen",
        "name": "阿里通义 DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-turbo"],
        "vision_models": ["qwen-vl-plus"],
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini", "gpt-4o"],
        "vision_models": ["gpt-4o-mini"],
    },
    {
        "id": "mock",
        "name": "Mock（本地联调，不调外部 API）",
        "base_url": "",
        "models": ["mock"],
        "vision_models": [],
    },
]

SENSITIVE_FIELDS = ("llm_api_key", "vision_api_key")

# 进程内生效配置（None 表示尚未从库加载，回落到 .env）
_runtime: Optional[dict] = None


def _env_snapshot() -> dict:
    """以 .env 为基准构造快照"""
    return {
        "llm_provider": settings.LLM_PROVIDER or "mock",
        "llm_api_key": settings.LLM_API_KEY or "",
        "llm_model": settings.LLM_MODEL or "",
        "llm_base_url": settings.LLM_BASE_URL or "",
        "vision_model": settings.VISION_MODEL or "",
        "vision_api_key": settings.VISION_API_KEY or "",
        "vision_base_url": settings.VISION_BASE_URL or "",
        "source": "env",
        "updated_at": None,
    }


def snapshot() -> dict:
    """同步读取当前生效配置（可能是 DB 覆盖后的）"""
    return dict(_runtime) if _runtime is not None else _env_snapshot()


def mask_key(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def _is_masked(value: str | None) -> bool:
    return bool(value) and "****" in value


async def _load_row(db: AsyncSession) -> Optional[SystemSetting]:
    return (await db.execute(
        select(SystemSetting).where(SystemSetting.id == 1)
    )).scalar_one_or_none()


async def reload(db: AsyncSession) -> dict:
    """从库加载配置到内存；库中未设置的字段回落到 .env"""
    global _runtime
    base = _env_snapshot()
    row = await _load_row(db)

    if row:
        for field in (
            "llm_provider", "llm_api_key", "llm_model", "llm_base_url",
            "vision_model", "vision_api_key", "vision_base_url",
        ):
            v = getattr(row, field)
            if v:  # 空值视为未覆盖，继续用 .env
                base[field] = v
        base["source"] = "db"
        base["updated_at"] = row.updated_at
    else:
        base["source"] = "env"

    _runtime = base
    return dict(_runtime)


def public_view(cfg: dict) -> dict:
    """给前端的视图：密钥掩码，并标记是否已配置"""
    out = dict(cfg)
    for f in SENSITIVE_FIELDS:
        raw = out.get(f) or ""
        out[f] = mask_key(raw)
        out[f.replace("_api_key", "_key_set")] = bool(raw)
    return out


async def update(db: AsyncSession, payload: dict, admin_id: int) -> dict:
    """
    更新配置。密钥字段传空或掩码表示不修改。
    """
    from datetime import datetime

    row = await _load_row(db)
    if not row:
        row = SystemSetting(id=1)
        db.add(row)
        await db.flush()

    for field in (
        "llm_provider", "llm_model", "llm_base_url",
        "vision_model", "vision_base_url",
    ):
        if field in payload and payload[field] is not None:
            setattr(row, field, str(payload[field]).strip() or None)

    for field in SENSITIVE_FIELDS:
        if field not in payload:
            continue
        value = payload[field]
        # 空串 / 掩码 → 保留原密钥；显式传 "-" 表示清空
        if value is None or value == "" or _is_masked(value):
            continue
        if value == "-":
            setattr(row, field, None)
        else:
            setattr(row, field, value.strip())

    row.updated_at = datetime.now()
    row.updated_by = admin_id
    await db.commit()
    return await reload(db)


# —————————— 连通性测试 ——————————
async def test_connection(
    *,
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
    kind: str = "llm",
) -> dict:
    """
    实际发起一次最小请求验证可用性。
    - provider=mock：直接返回成功（不联网）
    - api_key 传掩码/空：用已保存的密钥
    """
    cfg = snapshot()

    if not provider:
        raise ValidationError("请选择模型提供商")

    if provider == "mock":
        return {
            "ok": True,
            "latency_ms": 0,
            "reply": "mock 模式：不调用外部 API，无需测试连通性",
            "model": "mock",
            "base_url": "",
        }

    if _is_masked(api_key) or not api_key:
        api_key = cfg["vision_api_key"] if kind == "vision" else cfg["llm_api_key"]
    if not api_key:
        return {"ok": False, "latency_ms": 0, "error": "未填写 API Key"}

    if not model:
        return {"ok": False, "latency_ms": 0, "error": "未填写模型名称"}

    if not base_url:
        base_url = next(
            (p["base_url"] for p in PROVIDERS if p["id"] == provider), ""
        )
    if not base_url:
        return {"ok": False, "latency_ms": 0, "error": "未填写 Base URL"}

    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "只回复两个字：正常"}],
        "max_tokens": 16,
        "temperature": 0,
    }

    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
    except httpx.TimeoutException:
        return {
            "ok": False,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "error": f"请求超时（25s），请检查 Base URL 是否可达：{url}",
        }
    except Exception as e:
        return {
            "ok": False,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "error": f"请求失败：{e}",
        }

    elapsed = int((time.monotonic() - started) * 1000)

    if resp.status_code != 200:
        detail = resp.text[:300]
        hint = ""
        if resp.status_code in (401, 403):
            hint = "（API Key 无效或无权限）"
        elif resp.status_code == 404:
            hint = "（模型名或 Base URL 不正确）"
        elif resp.status_code == 429:
            hint = "（触发限流或额度用尽）"
        return {
            "ok": False,
            "latency_ms": elapsed,
            "error": f"HTTP {resp.status_code}{hint}：{detail}",
        }

    try:
        data = resp.json()
        reply = (data["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        return {"ok": False, "latency_ms": elapsed, "error": "响应不是预期的 JSON 结构"}

    return {
        "ok": True,
        "latency_ms": elapsed,
        "reply": reply[:200],
        "model": model,
        "base_url": base_url,
    }

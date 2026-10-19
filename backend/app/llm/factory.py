"""app/llm/factory.py — LLM Provider 工厂

配置来源：config_service.snapshot()（数据库 > .env，管理员在页面上改完即时生效）。
所有主流供应商都兼容 OpenAI 协议，统一走 OpenAICompatLLM。
"""
from __future__ import annotations

from app.llm.base import LLMProvider
from app.llm.openai_compat import OpenAICompatLLM

# 各供应商默认 base_url（未配置时兜底）
_DEFAULT_BASE_URLS = {
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
}

# 按配置签名缓存实例：配置一变，下一次调用自动重建
_cache: dict = {"sig": None, "llm": None}


def _build(cfg: dict) -> LLMProvider:
    provider = (cfg.get("llm_provider") or "mock").lower()

    if provider == "mock":
        from app.llm.mock import MockLLM
        return MockLLM()

    api_key = cfg.get("llm_api_key") or ""
    if not api_key:
        raise RuntimeError(
            "未配置 API Key。请在「模型配置」页面填写，"
            "或在 backend/.env 设置 LLM_PROVIDER=mock 做本地联调"
        )

    base_url = cfg.get("llm_base_url") or _DEFAULT_BASE_URLS.get(provider, "")
    if not base_url:
        raise RuntimeError(f"未知的模型提供商：{provider}，且未配置 Base URL")

    return OpenAICompatLLM(
        base_url=base_url,
        api_key=api_key,
        model=cfg.get("llm_model") or "",
    )


def get_llm() -> LLMProvider:
    from app.services import config_service

    cfg = config_service.snapshot()
    sig = (
        (cfg.get("llm_provider") or "").lower(),
        cfg.get("llm_model") or "",
        cfg.get("llm_base_url") or "",
        cfg.get("llm_api_key") or "",
    )
    if _cache["sig"] != sig or _cache["llm"] is None:
        _cache["llm"] = _build(cfg)
        _cache["sig"] = sig
    return _cache["llm"]


def invalidate_cache() -> None:
    """配置变更后调用（config_service.reload 已覆盖，这里保留手动入口）"""
    _cache["sig"] = None
    _cache["llm"] = None

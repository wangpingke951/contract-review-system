"""app/llm/factory.py — LLM Provider 工厂

按 settings.LLM_PROVIDER 返回对应实现。
目前所有主流供应商都兼容 OpenAI 协议，统一走 OpenAICompatLLM，
后续有特殊协议（如本地 vLLM 有差异）时在这里扩展分支。
"""
from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.llm.base import LLMProvider
from app.llm.openai_compat import OpenAICompatLLM

# 各供应商默认 base_url（.env 未配置时兜底）
_DEFAULT_BASE_URLS = {
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai": "https://api.openai.com/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
}


@lru_cache(maxsize=1)
def get_llm() -> LLMProvider:
    settings = get_settings()

    # mock 模式：本地联调，无需 API Key
    if settings.LLM_PROVIDER == "mock":
        from app.llm.mock import MockLLM
        return MockLLM()

    if not settings.LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY 未配置。开发联调可在 backend/.env 设置 LLM_PROVIDER=mock，"
            "或填入在线 API Key (LLM_PROVIDER=doubao|qwen|openai)"
        )
    base_url = settings.LLM_BASE_URL or _DEFAULT_BASE_URLS.get(settings.LLM_PROVIDER, "")
    if not base_url:
        raise RuntimeError(f"未知的 LLM_PROVIDER: {settings.LLM_PROVIDER}，且未配置 LLM_BASE_URL")
    return OpenAICompatLLM(
        base_url=base_url,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
    )

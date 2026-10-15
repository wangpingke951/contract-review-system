"""
app/llm/base.py — LLM Provider 抽象基类

所有在线 LLM API（豆包/通义/OpenAI）通过此抽象接入，
业务代码只依赖 chat() / stream_chat()，切换供应商只改 .env
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMProvider(ABC):
    """LLM 抽象基类（OpenAI Chat Completions 语义）"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int | None = None,
        response_json: bool = False,
    ) -> str:
        """
        非流式对话，返回完整回复文本
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        response_json: True 时要求模型输出 JSON
        """
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """流式对话（对话追问场景），逐段 yield 文本增量"""
        ...
        # 让函数成为 async generator
        yield ""

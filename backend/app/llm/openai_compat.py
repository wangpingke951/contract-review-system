"""
app/llm/openai_compat.py — OpenAI 兼容协议 LLM Provider

一份实现通吃三家（协议都是 OpenAI Chat Completions 兼容）：
- 字节豆包 Ark:     base_url=https://ark.cn-beijing.volces.com/api/v3
- 阿里通义 DashScope: base_url=https://dashscope.aliyuncs.com/compatible-mode/v1
- OpenAI:           base_url=https://api.openai.com/v1

切换只改 .env 的 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from app.llm.base import LLMProvider


class OpenAICompatLLM(LLMProvider):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        # 最近一次 chat 调用返回的 usage（token 统计用；流式调用不填）
        self.last_usage: dict = {}

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int | None = None,
        response_json: bool = False,
    ) -> str:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        if response_json:
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            self.last_usage = data.get("usage") or {}
            return data["choices"][0]["message"]["content"]

    async def stream_chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

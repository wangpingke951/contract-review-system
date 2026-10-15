"""
app/rag/embedding.py — Embedding Provider 抽象 + 双实现

- OpenAICompatEmbedding: 在线 API（豆包/通义/OpenAI，OpenAI embeddings 协议兼容）
- ChromaDefaultEmbedding: ChromaDB 内置本地模型（all-MiniLM-L6-v2，384 维）
  无 API Key 时的开发兜底，中文效果较弱，仅供本地联调

⚠️ 两种实现维度不同（1024 vs 384），切换 provider 后必须清空 ChromaDB collection 重建
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from functools import lru_cache

import httpx

from app.config import get_settings


class BaseEmbedding(ABC):
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量向量化，返回与输入等长的向量列表"""
        ...

    async def embed_text(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]


class OpenAICompatEmbedding(BaseEmbedding):
    """OpenAI embeddings 协议兼容（豆包 Ark / 通义 DashScope / OpenAI）"""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
        # 按 index 排序还原顺序
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]


class ChromaDefaultEmbedding(BaseEmbedding):
    """ChromaDB 内置默认模型（本地推理，首次使用会自动下载 ~80MB onnx 模型）"""

    def __init__(self):
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        self._ef = DefaultEmbeddingFunction()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # chroma EF 是同步阻塞的，丢线程池避免卡事件循环
        return await asyncio.to_thread(self._ef, texts)


@lru_cache(maxsize=1)
def get_embedding() -> BaseEmbedding:
    settings = get_settings()
    if settings.EMBEDDING_PROVIDER == "online" and settings.EMBEDDING_API_KEY:
        base_url = settings.EMBEDDING_BASE_URL or "https://ark.cn-beijing.volces.com/api/v3"
        return OpenAICompatEmbedding(
            base_url=base_url,
            api_key=settings.EMBEDDING_API_KEY,
            model=settings.EMBEDDING_MODEL,
        )
    # 无 Key 时降级到本地模型（仅开发联调用）
    return ChromaDefaultEmbedding()

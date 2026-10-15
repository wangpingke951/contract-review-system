"""
app/rag/vectorstore.py — ChromaDB 向量库封装

本地开发：embedded 模式（PersistentClient，单进程，数据落 CHROMA_PERSIST_DIR）
生产：http 模式（HttpClient 连 standalone server，避免多进程 SQLite 并发锁）

collection: knowledge_chunks
- 每条 = 一个知识条目 chunk
- metadata: source_doc_id / source_filename / category / section_title / chunk_index
- id 规则: "{source_doc_id}_{chunk_index}"（同一文档重复上传时 upsert 覆盖）
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

import chromadb

from app.config import get_settings

COLLECTION_NAME = "knowledge_chunks"


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.ClientAPI:
    settings = get_settings()
    if settings.CHROMA_MODE == "http":
        return chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    return chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)


def get_collection():
    """获取知识库 collection（不存在则创建）"""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(
    chunks: list[str],
    metadatas: list[dict],
    embeddings: Optional[list[list[float]]] = None,
    ids: Optional[list[str]] = None,
) -> list[str]:
    """
    写入/更新 chunks
    - embeddings 为 None 时使用 collection 默认 EF（本地模型）
    - ids 未提供时自动生成 "{source_doc_id}_{chunk_index}"
    返回实际写入的 id 列表
    """
    if not chunks:
        return []
    if ids is None:
        ids = [
            f"{m.get('source_doc_id', 'unknown')}_{m.get('chunk_index', i)}"
            for i, m in enumerate(metadatas)
        ]
    col = get_collection()
    kwargs: dict[str, Any] = {"documents": chunks, "metadatas": metadatas, "ids": ids}
    if embeddings is not None:
        kwargs["embeddings"] = embeddings
    col.upsert(**kwargs)
    return ids


def delete_by_source(source_doc_id: str) -> None:
    """按来源文档删除其全部 chunks（知识文档删除时调用）"""
    col = get_collection()
    col.delete(where={"source_doc_id": {"$eq": str(source_doc_id)}})


def similarity_search(
    query_embedding: Optional[list[float]],
    query_text: Optional[str],
    k: int = 8,
    min_similarity: float = 0.65,
    where: Optional[dict] = None,
) -> list[dict]:
    """
    相似度检索
    - 二选一：query_embedding（在线 provider）/ query_text（本地 EF 自己向量化）
    - min_similarity: 余弦相似度阈值（chroma 返回 cosine distance = 1 - 相似度）
    返回 [{id, text, metadata, similarity}]，按相似度降序
    """
    col = get_collection()
    n_total = col.count()
    if n_total == 0:
        return []

    kwargs: dict[str, Any] = {
        "n_results": min(k, n_total),
        "include": ["documents", "metadatas", "distances"],
    }
    if query_embedding is not None:
        kwargs["query_embeddings"] = [query_embedding]
    else:
        kwargs["query_texts"] = [query_text or ""]
    if where:
        kwargs["where"] = where

    res = col.query(**kwargs)

    results: list[dict] = []
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    ids = res.get("ids", [[]])[0]
    for doc_id, doc, meta, dist in zip(ids, docs, metas, dists):
        similarity = 1.0 - dist  # cosine distance → similarity
        if similarity >= min_similarity:
            results.append({
                "id": doc_id,
                "text": doc,
                "metadata": meta,
                "similarity": round(similarity, 4),
            })
    return results


def count_chunks() -> int:
    return get_collection().count()

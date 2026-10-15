"""
app/rag/retriever.py — 检索层

审查时的检索策略（技术架构设计 5.3 / 5.4）：
- 多维度分解 query → 各维度独立检索 top-K → 合并去重 → 阈值过滤
- 维度清单对应默认风险类别（条款缺失/金额/期限/主体/违约/知产/保密/不可抗力/争议）
"""
from __future__ import annotations

from app.rag import vectorstore
from app.rag.embedding import get_embedding

# 审查维度（维度名 → 检索 query 描述）
REVIEW_DIMENSIONS = [
    ("条款缺失", "合同应包含的关键条款（争议解决、违约责任、保密、不可抗力等）是否缺失"),
    ("金额异常", "合同金额、计费方式、付款条件是否明确合理，是否存在金额模糊或不利条款"),
    ("期限风险", "合同期限、履行期限、自动续约条款是否对我方不利"),
    ("主体资格", "签约主体名称、资质、签章要求是否清晰合规"),
    ("违约责任", "违约责任是否对等，是否存在过度倾斜一方的情形"),
    ("知识产权", "知识产权归属、成果使用许可是否合理"),
    ("保密条款", "保密义务范围、期限、责任是否合理对等"),
    ("不可抗力", "不可抗力的定义、通知义务、后果分担是否合理"),
    ("争议解决", "管辖法院或仲裁地选择是否对我方不利"),
]

# chroma cosine distance → similarity；0.65 相似度 = 0.35 距离
MIN_SIMILARITY = 0.65
TOP_K_PER_DIM = 8


async def retrieve_for_review(contract_text: str) -> dict[str, list[dict]]:
    """
    为一次审查执行多维度检索
    返回 {维度名: [evidence, ...]}
    知识库为空时返回 {}（调用方走无 RAG 降级路径）
    """
    if vectorstore.count_chunks() == 0:
        return {}

    embedding = get_embedding()
    evidences: dict[str, list[dict]] = {}
    seen_ids: set[str] = set()

    for dim_name, dim_desc in REVIEW_DIMENSIONS:
        query = f"{dim_desc}。合同内容摘要：{contract_text[:300]}"
        vec = await embedding.embed_text(query)
        hits = vectorstore.similarity_search(
            query_embedding=vec,
            query_text=None,
            k=TOP_K_PER_DIM,
            min_similarity=MIN_SIMILARITY,
        )
        # 跨维度去重：同一条知识只挂在第一次命中的维度下
        deduped = []
        for h in hits:
            if h["id"] not in seen_ids:
                seen_ids.add(h["id"])
                deduped.append(h)
        if deduped:
            evidences[dim_name] = deduped

    return evidences


async def retrieve_for_chat(question: str, k: int = 6) -> list[dict]:
    """对话追问时的检索：单 query，返回证据列表"""
    if vectorstore.count_chunks() == 0:
        return []
    embedding = get_embedding()
    vec = await embedding.embed_text(question)
    return vectorstore.similarity_search(
        query_embedding=vec,
        query_text=None,
        k=k,
        min_similarity=0.55,  # 对话场景阈值稍宽松
    )

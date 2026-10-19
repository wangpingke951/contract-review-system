"""
app/rag/review_chain.py — 审查链：检索证据 + 合同原文 → LLM → 结构化风险报告

Prompt 设计：
- system: 角色设定 + 输出 JSON schema 约束
- user: 各维度知识依据 + 合同全文 + 审查指令
- 知识库无命中时走通用规则审查（不阻断，报告会提示）
"""
from __future__ import annotations

import json
import re

from app.llm.factory import get_llm
from app.rag.retriever import retrieve_for_review

SYSTEM_PROMPT = """你是资深合同审查专家，精通中国合同法律实务。你的任务是根据审查指引和知识依据，对合同进行全面风险审查。

输出要求：只输出一个 JSON 对象，不要输出任何其他文字、解释或 markdown 代码块标记。JSON 格式：
{
  "overall_risk": "high|medium|low",
  "risk_items": [
    {
      "category_name": "风险类别名（如：条款缺失、金额异常、期限风险、违约责任、知识产权、保密条款、不可抗力、争议解决、付款条款等）",
      "risk_level": "high|medium|low",
      "contract_snippet": "合同原文中存在问题的关键片段（截取原文，不超过100字）",
      "issue": "问题说明：为什么这是风险",
      "suggestion": "具体可执行的修改建议",
      "is_positive": false,
      "source_knowledge_ids": ["命中的知识条目ID，没有则空数组"]
    }
  ]
}

审查规则：
1. 逐条检查合同的主要条款，重点识别：缺失的关键条款、对一方明显不利的条款、表述模糊易生争议的条款
2. 每条风险必须引用合同原文片段（contract_snippet 从原文截取）
3. 也应报告合同中值得肯定的合规条款（is_positive=true）
4. risk_items 数量控制在 3-10 条，按风险严重程度排序
5. 给出的修改建议必须具体、可执行，不要空泛
6. overall_risk 按全部风险项的最高级别判定"""


def _build_user_prompt(contract_text: str, evidences: dict[str, list[dict]]) -> str:
    parts: list[str] = []

    if evidences:
        parts.append("## 审查知识依据（来自知识库检索）")
        for dim_name, evs in evidences.items():
            parts.append(f"\n### 维度：{dim_name}")
            for ev in evs:
                meta = ev.get("metadata", {})
                source = meta.get("source_filename", "未知来源")
                parts.append(f"- [知识ID:{ev['id']} | 来源:{source} | 相似度:{ev['similarity']}]")
                parts.append(f"  {ev['text'][:400]}")
        parts.append("")
    else:
        parts.append("## 审查知识依据")
        parts.append("（知识库暂无命中内容，请基于通用合同审查规则进行审查）\n")

    parts.append("## 待审查合同全文")
    parts.append("```")
    parts.append(contract_text[:8000])  # 控制长度，超出截断
    parts.append("```")
    parts.append("")
    parts.append("请按照系统指令输出 JSON 格式的审查报告。")
    return "\n".join(parts)


def _extract_json(text: str) -> dict:
    """健壮的 JSON 提取：容忍 markdown 代码块包裹、前后杂文"""
    text = text.strip()
    # 去掉 ```json ... ``` 包裹
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        # 找第一个 { 到最后一个 }
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    return json.loads(text)


async def run_review(
    contract_text: str,
    dimensions: list[tuple[str, str]] | None = None,
) -> dict:
    """
    执行完整审查：
    1. 多维度检索知识库（维度可由审查模板配置）
    2. 构造 Prompt → LLM
    3. 解析 JSON → {"overall_risk": ..., "risk_items": [...]}
    """
    evidences = await retrieve_for_review(contract_text, dimensions)
    user_prompt = _build_user_prompt(contract_text, evidences)

    llm = get_llm()
    raw = await llm.chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_json=True,
    )

    report = _extract_json(raw)

    # 校验/兜底结构
    if "risk_items" not in report or not isinstance(report["risk_items"], list):
        raise ValueError("LLM 返回的 JSON 缺少 risk_items 字段")
    valid_levels = {"high", "medium", "low"}
    for item in report["risk_items"]:
        item["risk_level"] = item.get("risk_level") if item.get("risk_level") in valid_levels else "medium"
        item["is_positive"] = bool(item.get("is_positive", False))
        item.setdefault("source_knowledge_ids", [])
        item.setdefault("category_name", "其他")

    # 总体风险等级按 PRD 4.3 规则由高风险条数决定，不采用模型自评（保证同一份合同结论稳定）
    # ≥3 条高风险 → 高；1–2 条 → 中；0 条 → 低
    high_count = sum(
        1 for it in report["risk_items"]
        if not it["is_positive"] and it["risk_level"] == "high"
    )
    report["overall_risk"] = "high" if high_count >= 3 else ("medium" if high_count >= 1 else "low")
    report["high_risk_count"] = high_count
    report["has_rag_evidence"] = bool(evidences)
    return report

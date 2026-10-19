"""
app/llm/mock.py — Mock LLM Provider（本地开发联调用）

LLM_PROVIDER=mock 时启用：
- 审查场景：从**合同原文**里真实截取片段作为风险项依据（保证原文高亮、
  版本对比的问题闭环能跑通），而不是返回写死的字符串
- 对话场景：返回固定的模拟回答

不消耗 API 费用，用于前后端联调和端到端测试。
生产环境切换 LLM_PROVIDER=doubao|qwen|openai 即可。
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from app.llm.base import LLMProvider

# 风险项模板：按关键词在原文里找对应段落作为 snippet
_ITEM_TEMPLATES = [
    {
        "category_name": "付款条款",
        "risk_level": "high",
        "keywords": ["付款", "支付", "货款", "价款", "发票"],
        "issue": "付款节点与验收、质保脱钩，一次性全额付款对付款方风险过高",
        "suggestion": "改为验收合格后分期支付，并预留 5%-10% 质保金至质保期满",
        "is_positive": False,
    },
    {
        "category_name": "违约责任",
        "risk_level": "medium",
        "keywords": ["违约", "赔偿", "责任"],
        "issue": "违约责任表述单一，未区分迟延、质量不合格等情形，缺少按日计罚标准",
        "suggestion": "区分违约情形设置责任，迟延交付建议按日 0.05% 计罚并设上限",
        "is_positive": False,
    },
    {
        "category_name": "争议解决",
        "risk_level": "low",
        "keywords": ["争议", "管辖", "仲裁", "法院", "诉讼"],
        "issue": "争议解决条款已明确，但需确认管辖地与合同履行存在实际连接点",
        "suggestion": "优先约定我方所在地有管辖权的法院，避免异地诉讼成本",
        "is_positive": False,
    },
    {
        "category_name": "合同结构",
        "risk_level": "low",
        "keywords": ["第一条", "合同", "甲方", "乙方"],
        "issue": "合同基本框架完整，主要条款齐备",
        "suggestion": "保持现有结构，后续可补充保密与不可抗力条款",
        "is_positive": True,
    },
]

_MOCK_CHAT_ANSWER = (
    "根据审查报告，主要风险集中在付款节点与验收、质保的脱钩：一次性付款使付款方"
    "在交付质量出问题时缺乏制约手段。参考行业惯例，建议改为验收合格后支付 90%，"
    "预留 10% 质保金在质保期满后支付。\n\n"
    "（当前为 mock 模式回复，配置真实 LLM API Key 后将返回基于知识库的正式回答）"
)


def _extract_contract(messages: list[dict]) -> str:
    """从 user prompt 里取出待审查合同全文"""
    for m in messages:
        if m.get("role") != "user":
            continue
        content = m.get("content") or ""
        if "## 待审查合同全文" not in content:
            continue
        body = content.split("## 待审查合同全文", 1)[1]
        # 去掉 ``` 代码块包裹和尾部指令
        if "```" in body:
            body = body.split("```", 2)[1] if body.count("```") >= 2 else body.replace("```", "")
        body = body.split("请按照系统指令输出")[0]
        return body.strip()
    return ""


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n") if len(p.strip()) >= 12]


def _pick_snippet(paras: list[str], keywords: list[str], used: set[int]) -> str:
    """按关键词找未被占用的段落，找不到就退而取第一条未占用段落"""
    for kw in keywords:
        for i, p in enumerate(paras):
            if i in used:
                continue
            if kw in p:
                used.add(i)
                return p[:80]
    for i, p in enumerate(paras):
        if i not in used:
            used.add(i)
            return p[:80]
    return ""


def _build_mock_report(messages: list[dict]) -> dict:
    contract = _extract_contract(messages)
    paras = _paragraphs(contract)
    used: set[int] = set()

    items = []
    for tpl in _ITEM_TEMPLATES:
        snippet = _pick_snippet(paras, tpl["keywords"], used) if paras else ""
        if not snippet:
            continue
        items.append({
            "category_name": tpl["category_name"],
            "risk_level": tpl["risk_level"],
            "contract_snippet": snippet,
            "issue": tpl["issue"],
            "suggestion": tpl["suggestion"],
            "is_positive": tpl["is_positive"],
            "source_knowledge_ids": [],
        })

    # 按 PRD 4.3 规则由高风险条数决定总体等级
    high = sum(1 for i in items if not i["is_positive"] and i["risk_level"] == "high")
    overall = "high" if high >= 3 else ("medium" if high >= 1 else "low")

    return {"overall_risk": overall, "risk_items": items}


class MockLLM(LLMProvider):
    async def chat(self, messages, temperature=0.3, max_tokens=None, response_json=False):
        await asyncio.sleep(0.5)  # 模拟推理延迟
        if response_json:
            return json.dumps(_build_mock_report(messages), ensure_ascii=False)
        return _MOCK_CHAT_ANSWER

    async def stream_chat(self, messages, temperature=0.3, max_tokens=None):
        answer = _MOCK_CHAT_ANSWER
        step = 8
        for i in range(0, len(answer), step):
            yield answer[i : i + step]
            await asyncio.sleep(0.05)

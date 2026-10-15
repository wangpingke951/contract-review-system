"""
app/llm/mock.py — Mock LLM Provider（本地开发联调用）

LLM_PROVIDER=mock 时启用：返回固定的模拟审查报告 JSON，
不消耗 API 费用，用于前后端联调和端到端测试。
生产环境切换 LLM_PROVIDER=doubao|qwen|openai 即可。
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from app.llm.base import LLMProvider

_MOCK_REVIEW_JSON = {
    "overall_risk": "high",
    "risk_items": [
        {
            "category_name": "付款条款",
            "risk_level": "high",
            "contract_snippet": "乙方发货后 30 日内，甲方支付全额货款",
            "issue": "货到后一次性全额付款对采购方风险过高，缺乏验收环节和履约保障",
            "suggestion": "改为验收合格后分期支付，并保留 5%-10% 质保金至质保期满",
            "is_positive": False,
        },
        {
            "category_name": "违约责任",
            "risk_level": "medium",
            "contract_snippet": "任何一方违反本合同约定，应向对方支付合同总金额 5% 的违约金",
            "issue": "违约金比例单一，未区分迟延交付、质量不合格等不同违约情形，且无按日计罚标准",
            "suggestion": "区分违约情形设置不同违约责任，迟延交付建议按日 0.05% 计罚",
            "is_positive": False,
        },
        {
            "category_name": "争议解决",
            "risk_level": "low",
            "contract_snippet": "提交北京市海淀区人民法院诉讼解决",
            "issue": "管辖法院已明确，约定方式合法有效",
            "suggestion": "确认海淀区法院与合同履行的实际连接点，避免管辖异议",
            "is_positive": False,
        },
        {
            "category_name": "合同结构",
            "risk_level": "low",
            "contract_snippet": "合同包含标的、金额、付款、违约责任、争议解决条款",
            "issue": "合同基本框架完整，主要条款齐备",
            "suggestion": "保持现有结构，后续可补充保密与不可抗力条款",
            "is_positive": True,
        },
    ],
}

_MOCK_CHAT_ANSWER = (
    "根据审查报告，本合同最主要的付款风险在于「货到后 30 日内支付全额货款」，"
    "该条款缺乏验收环节。参考行业惯例，建议改为验收合格后支付 90%，"
    "预留 10% 质保金在质保期满后支付。\n\n"
    "（当前为 mock 模式回复，配置真实 LLM API Key 后将返回基于知识库的正式回答）"
)


class MockLLM(LLMProvider):
    async def chat(self, messages, temperature=0.3, max_tokens=None, response_json=False):
        await asyncio.sleep(0.5)  # 模拟推理延迟
        if response_json:
            return json.dumps(_MOCK_REVIEW_JSON, ensure_ascii=False)
        return _MOCK_CHAT_ANSWER

    async def stream_chat(self, messages, temperature=0.3, max_tokens=None):
        answer = _MOCK_CHAT_ANSWER
        step = 8
        for i in range(0, len(answer), step):
            yield answer[i : i + step]
            await asyncio.sleep(0.05)

"""
app/services/diff_service.py — 合同版本比对与问题闭环

两个能力：
1. 段落级文本差异（新增 / 删除 / 改写），用于展示「这一版改了什么」
2. 问题闭环：把上一版审查报告里的风险项逐条对照新版合同，
   判定「仍存在 / 已改写 / 疑似已修复 / 需人工复核」

判定口径（宁可保守，不谎报"已修复"）：
- 旧片段在新版原文中原样出现            → persists（仍存在）
- 片段消失，但存在相似度 ≥0.75 的段落    → changed（已改写，需复核措辞是否解决）
- 片段消失且无相似段落                  → resolved（原文已不存在，疑似已修复）
- 旧风险项本身没有原文片段（如"条款缺失"）→ unknown（需人工复核）
"""
from __future__ import annotations

from difflib import SequenceMatcher

SIMILAR_CHANGED = 0.75
MAX_SEGMENTS = 300
MAX_SNIPPET_LEN = 200


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in (text or "").split("\n") if p.strip()]


def diff_paragraphs(old_text: str, new_text: str) -> dict:
    """段落级 diff，返回摘要 + 变更片段"""
    old_paras = _paragraphs(old_text)
    new_paras = _paragraphs(new_text)

    sm = SequenceMatcher(None, old_paras, new_paras, autojunk=False)
    segments: list[dict] = []
    counts = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            counts["unchanged"] += i2 - i1
            continue
        if tag == "delete":
            counts["removed"] += i2 - i1
            segments.append({"type": "removed", "text": "\n".join(old_paras[i1:i2])})
        elif tag == "insert":
            counts["added"] += j2 - j1
            segments.append({"type": "added", "text": "\n".join(new_paras[j1:j2])})
        else:  # replace
            counts["changed"] += max(i2 - i1, j2 - j1)
            segments.append({
                "type": "changed",
                "old_text": "\n".join(old_paras[i1:i2]),
                "text": "\n".join(new_paras[j1:j2]),
            })

    return {
        "summary": counts,
        "segments": segments[:MAX_SEGMENTS],
        "truncated": len(segments) > MAX_SEGMENTS,
        "total_segments": len(segments),
    }


def _best_match(snippet: str, paras: list[str]) -> tuple[float, str | None]:
    """在新版段落里找与旧片段最相似的一段"""
    best_ratio, best_para = 0.0, None
    snip = snippet[:MAX_SNIPPET_LEN]
    for p in paras:
        ratio = SequenceMatcher(None, snip, p[:MAX_SNIPPET_LEN], autojunk=False).ratio()
        if ratio > best_ratio:
            best_ratio, best_para = ratio, p
        if ratio >= 0.999:
            break
    return best_ratio, best_para


def check_closure(old_items: list, new_text: str) -> list[dict]:
    """
    逐条判定旧报告风险项在新版合同中的状态。
    old_items: RiskItem ORM 列表
    """
    paras = _paragraphs(new_text)
    results: list[dict] = []

    for item in old_items:
        snippet = (item.contract_snippet or "").strip()
        base = {
            "item_id": item.id,
            "risk_level": item.risk_level.value,
            "category_name": item.category_name,
            "issue": item.issue,
            "snippet": snippet[:MAX_SNIPPET_LEN],
        }

        if item.is_positive:
            base.update(status="positive", reason="正向发现，不参与问题闭环", similarity=1.0)
            results.append(base)
            continue

        if not snippet:
            base.update(
                status="unknown",
                reason="该类问题没有对应的原文片段（如条款缺失），需人工复核",
                similarity=0.0,
            )
            results.append(base)
            continue

        if snippet in new_text:
            base.update(status="persists", reason="原片段仍出现在新版合同中", similarity=1.0)
            results.append(base)
            continue

        ratio, matched = _best_match(snippet, paras)
        if ratio >= SIMILAR_CHANGED:
            base.update(
                status="changed",
                reason=f"原文已改写（相似度 {ratio:.0%}），需确认修改后是否已解决该风险",
                similarity=round(ratio, 3),
                matched_text=(matched or "")[:MAX_SNIPPET_LEN],
            )
        else:
            base.update(
                status="resolved",
                reason="新版合同中已找不到该片段，疑似已修复，建议人工确认",
                similarity=round(ratio, 3),
            )
        results.append(base)

    return results


def summarize_closure(items: list[dict]) -> dict:
    summary = {"resolved": 0, "changed": 0, "persists": 0, "unknown": 0, "positive": 0}
    for it in items:
        summary[it["status"]] = summary.get(it["status"], 0) + 1
    return summary

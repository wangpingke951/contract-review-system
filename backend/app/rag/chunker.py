"""
app/rag/chunker.py — 知识文档切块

策略（技术架构设计 5.2）：
1. 一级：按条款切（第X条 / 一、 / 1. 等标题模式），条款完整不截断
2. 二级：字数兜底 — 上限 1000 中文字（超长在句号处软切），下限 200 字（合并相邻短块）
3. metadata 保留溯源: source_doc_id / source_filename / category / section_title
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# 条款标题模式（与 pdf_parser 保持一致的识别口径）
_TITLE_RE = re.compile(
    r"^(第[一二三四五六七八九十百千万\d]+条"
    r"|[一二三四五六七八九十]+、"
    r"|（[一二三四五六七八九十]+）"
    r"|\d+\.\d+\s"
    r"|\d+[、.]\s*"
    r"|(第[一二三四五六七八九十]+章)"
    r"|(总则|附则|违约责任|争议解决|保密条款|不可抗力|知识产权|生效|终止))"
)

MAX_CHUNK_CHARS = 1000
MIN_CHUNK_CHARS = 200


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)


def _soft_split_long(text: str, max_chars: int) -> list[str]:
    """超长块在句号处软切"""
    sentences = re.split(r"(?<=[。；;])", text)
    parts: list[str] = []
    buf = ""
    for s in sentences:
        if len(buf) + len(s) > max_chars and buf:
            parts.append(buf)
            buf = s
        else:
            buf += s
    if buf:
        parts.append(buf)
    return parts


def chunk_knowledge_text(
    text: str,
    source_doc_id: int | str,
    source_filename: str,
    category: str,
) -> list[Chunk]:
    """
    知识文档 → chunk 列表
    每条 chunk 的 metadata 由调用方补充写入 ChromaDB
    """
    text = (text or "").strip()
    if not text:
        return []

    # 1) 按标题模式切成条款段
    lines = text.split("\n")
    sections: list[tuple[str, list[str]]] = []  # (title, lines)
    current_title = "概述"
    current_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _TITLE_RE.match(stripped) and len(stripped) < 80:
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = stripped[:60]
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, current_lines))

    # 2) 条款段 → chunk（超长软切 / 过短合并）
    raw_chunks: list[tuple[str, str]] = []  # (section_title, chunk_text)
    pending_title = sections[0][0] if sections else "概述"
    pending_parts: list[str] = []

    def flush_pending():
        nonlocal pending_parts
        if pending_parts:
            raw_chunks.append((pending_title, "\n".join(pending_parts)))
            pending_parts = []

    for title, seg_lines in sections:
        seg_text = "\n".join(seg_lines).strip()
        if len(seg_text) > MAX_CHUNK_CHARS:
            flush_pending()
            for part in _soft_split_long(seg_text, MAX_CHUNK_CHARS):
                raw_chunks.append((title, part))
        elif len(seg_text) < MIN_CHUNK_CHARS:
            # 短块挂起，与相邻段合并
            if pending_parts and len("\n".join(pending_parts)) >= MIN_CHUNK_CHARS:
                flush_pending()
                pending_title = title
            pending_parts.append(seg_text)
        else:
            flush_pending()
            raw_chunks.append((title, seg_text))
    flush_pending()

    # 3) 组装 Chunk + metadata
    chunks: list[Chunk] = []
    for i, (title, ctext) in enumerate(raw_chunks):
        chunks.append(Chunk(
            text=ctext,
            metadata={
                "source_doc_id": str(source_doc_id),
                "source_filename": source_filename,
                "category": category,
                "section_title": title,
                "chunk_index": i,
            },
        ))
    return chunks

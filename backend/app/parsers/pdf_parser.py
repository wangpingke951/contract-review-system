"""PDF 解析器 — pdfplumber"""
from __future__ import annotations

import re
from typing import List
from app.parsers.base import (
    ContractParser,
    StructuredContract,
    ContractSection,
    SectionLevel,
    detect_chinese_ratio,
)


# 标题识别规则（条款式合同的常见模式）
TITLE_PATTERNS = [
    # 第一条 / 第二条 / 第三条 ...
    (r"^第[一二三四五六七八九十百千万\d]+条", SectionLevel.TOP),
    # 一、 二、 三、 ...  或 （一）（二）
    (r"^[一二三四五六七八九十]+、", SectionLevel.TOP),
    (r"^（[一二三四五六七八九十]+）", SectionLevel.SUB),
    # 1. 2. 3. ... 或 1.1 1.2
    (r"^\d+\.\d+\s", SectionLevel.SUB),
    (r"^\d+\.\s", SectionLevel.TOP),
    # 第一章 / 第二章 / 总则 / 附则 / 违约责任 / 争议解决 等关键词
    (r"^(总则|附则|违约责任|争议解决|合同标的|保密条款|不可抗力|知识产权|生效|终止)", SectionLevel.TOP),
]


class PDFParser(ContractParser):
    SUPPORTED_EXTENSIONS = {"pdf"}

    async def parse(self, file_path: str) -> StructuredContract:
        import pdfplumber

        errors: List[str] = []
        raw_text_parts: List[str] = []

        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    raw_text_parts.append(text)
        except Exception as e:
            errors.append(f"PDF 解析失败: {e}")
            return StructuredContract(raw_text="", parse_errors=errors)

        raw_text = "\n".join(raw_text_parts)
        sections = self._split_sections(raw_text)

        chinese_ratio = detect_chinese_ratio(raw_text)
        language = "zh-CN" if chinese_ratio > 0.3 else "unknown"

        return StructuredContract(
            raw_text=raw_text,
            sections=sections,
            word_count=len(raw_text),
            language=language,
            parse_errors=errors,
        )

    def _split_sections(self, raw_text: str) -> List[ContractSection]:
        """按标题模式切分章节"""
        lines = raw_text.split("\n")
        sections: List[ContractSection] = []
        current_title = "合同正文"
        current_level = SectionLevel.TOP
        current_content_lines: List[str] = []
        char_offset = 0

        # 预计算每行的全局字符偏移
        line_offsets = []
        acc = 0
        for line in lines:
            line_offsets.append(acc)
            acc += len(line) + 1  # +1 for newline

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # 检查是否匹配标题模式
            matched_title = False
            for pattern, level in TITLE_PATTERNS:
                if re.match(pattern, stripped):
                    # 保存上一个 section
                    if current_content_lines:
                        content = "\n".join(current_content_lines)
                        sections.append(ContractSection(
                            title=current_title,
                            level=current_level,
                            content=content,
                            char_start=line_offsets[i - len(current_content_lines)],
                            char_end=line_offsets[i - 1] + len(lines[i - 1]),
                        ))
                    current_title = stripped[:60]  # 截断过长的标题
                    current_level = level
                    current_content_lines = []
                    matched_title = True
                    break

            if not matched_title:
                current_content_lines.append(line)

        # 最后一个 section
        if current_content_lines:
            content = "\n".join(current_content_lines)
            sections.append(ContractSection(
                title=current_title,
                level=current_level,
                content=content,
                char_start=line_offsets[len(lines) - len(current_content_lines)],
                char_end=len(raw_text),
            ))

        # 如果没识别到任何标题（纯文本无条款格式），把整份文档作为一个 section
        if not sections:
            sections.append(ContractSection(
                title="合同全文",
                level=SectionLevel.TOP,
                content=raw_text,
                char_start=0,
                char_end=len(raw_text),
            ))

        return sections

"""DOCX 解析器 — python-docx"""
from __future__ import annotations

from typing import List
from app.parsers.base import (
    ContractParser,
    StructuredContract,
    ContractSection,
    SectionLevel,
    detect_chinese_ratio,
)


class DocxParser(ContractParser):
    SUPPORTED_EXTENSIONS = {"docx"}

    async def parse(self, file_path: str) -> StructuredContract:
        from docx import Document

        errors: List[str] = []

        try:
            doc = Document(file_path)
        except Exception as e:
            errors.append(f"DOCX 解析失败: {e}")
            return StructuredContract(raw_text="", parse_errors=errors)

        raw_text_parts: List[str] = []
        sections: List[ContractSection] = []

        current_title = "合同正文"
        current_level = SectionLevel.TOP
        current_content_lines: List[str] = []
        char_offset = 0

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            raw_text_parts.append(text)

            # 检查样式或文本特征
            style_name = para.style.name if para.style else ""

            is_heading = (
                style_name.startswith("Heading")
                or style_name.startswith("heading")
                or self._looks_like_title(text)
            )

            if is_heading and len(text) < 80:
                # 保存上一个 section
                if current_content_lines:
                    content = "\n".join(current_content_lines)
                    sections.append(ContractSection(
                        title=current_title,
                        level=current_level,
                        content=content,
                        char_start=char_offset,
                        char_end=char_offset + len(content),
                    ))
                    char_offset += len(content) + 1

                # 判断层级
                if "Heading 1" in style_name:
                    current_level = SectionLevel.TOP
                elif "Heading 2" in style_name:
                    current_level = SectionLevel.SUB
                else:
                    current_level = SectionLevel.TOP

                current_title = text[:60]
                current_content_lines = []
            else:
                current_content_lines.append(text)

        # 最后一个
        if current_content_lines:
            content = "\n".join(current_content_lines)
            sections.append(ContractSection(
                title=current_title,
                level=current_level,
                content=content,
                char_start=char_offset,
                char_end=char_offset + len(content),
            ))

        raw_text = "\n".join(raw_text_parts)
        chinese_ratio = detect_chinese_ratio(raw_text)
        language = "zh-CN" if chinese_ratio > 0.3 else "unknown"

        return StructuredContract(
            raw_text=raw_text,
            sections=sections,
            word_count=len(raw_text),
            language=language,
            parse_errors=errors,
        )

    @staticmethod
    def _looks_like_title(text: str) -> bool:
        """启发式判断某段文本是否像标题"""
        if len(text) <= 60 and len(text) >= 2:
            first = text[0]
            # 以 "第"、"一"~"九"、数字、"总则/附则" 开头
            if first in "一二三四五六七八九十" or first.isdigit() or first == "第":
                return True
            keywords = ["总则", "附则", "违约", "争议", "保密", "标的", "期限", "生效"]
            for kw in keywords:
                if kw in text:
                    return True
        return False

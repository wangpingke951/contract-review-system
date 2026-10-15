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
            errors.append(
                "Word 文档解析失败：文件可能已损坏或不是有效的 .docx 格式"
                f"（旧版 .doc 请另存为 .docx 后上传）。原始信息：{e}"
            )
            return StructuredContract(raw_text="", parse_errors=errors)

        raw_text_parts: List[str] = []
        sections: List[ContractSection] = []

        current_title = "合同正文"
        current_level = SectionLevel.TOP
        current_lines: List[str] = []
        char_offset = 0

        def flush() -> None:
            """把当前累积的行收成一个 section

            关键：标题行本身也计入 content。
            否则像「第一条 服务内容」紧接着「第二条 合同金额」这种逐条列出的合同，
            两条标题之间没有任何正文行，section 会因为内容为空而被整体丢弃，
            最终只剩极少几个 section（章节树失效）。
            """
            nonlocal char_offset
            if not current_lines:
                return
            content = "\n".join(current_lines)
            sections.append(ContractSection(
                title=current_title,
                level=current_level,
                content=content,
                char_start=char_offset,
                char_end=char_offset + len(content),
            ))
            char_offset += len(content) + 1

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            raw_text_parts.append(text)

            style_name = para.style.name if para.style else ""
            is_heading_style = style_name.startswith("Heading") or style_name.startswith("heading")

            # 样式明确为标题的一律按标题处理（不再限制长度）；
            # 只有靠文本特征猜测的才加长度上限，避免把长段落误判成标题
            is_heading = is_heading_style or (
                len(text) < 80 and self._looks_like_title(text)
            )

            if is_heading:
                flush()

                if "Heading 2" in style_name:
                    current_level = SectionLevel.SUB
                elif "Heading 3" in style_name:
                    current_level = SectionLevel.DETAIL
                else:
                    current_level = SectionLevel.TOP

                current_title = text[:60]
                current_lines = [text]   # 标题行计入内容
            else:
                current_lines.append(text)

        flush()   # 最后一个 section

        raw_text = "\n".join(raw_text_parts)

        # 文档里没有可提取的文字（例如正文全是图片）
        if not raw_text.strip():
            errors.append(
                "未能从该 Word 文档中提取到文字内容。若正文为图片或截图，"
                "请导出为图片（PNG/JPG）后上传，系统会使用 OCR 识别"
            )
            return StructuredContract(raw_text="", parse_errors=errors)

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

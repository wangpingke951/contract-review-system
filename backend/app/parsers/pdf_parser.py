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
            errors.append(self._describe_open_error(e))
            return StructuredContract(raw_text="", parse_errors=errors)

        raw_text = "\n".join(raw_text_parts)

        # 无文本：多为扫描件/图片型 PDF，给出可操作的替代方案而不是笼统报错
        if not raw_text.strip():
            errors.append(
                "未能从该 PDF 中提取到文字内容。若为扫描件或图片型 PDF，"
                "请将页面导出为图片（PNG/JPG）后上传，系统会使用 OCR 识别"
            )
            return StructuredContract(raw_text="", parse_errors=errors)

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

    @staticmethod
    def _describe_open_error(e: Exception) -> str:
        """把底层异常翻译成用户能看懂、能行动的提示"""
        name = type(e).__name__
        low = f"{name} {e}".lower()
        if "password" in low or "encrypt" in low:
            return "该 PDF 已加密，系统无法读取，请提供解密版本后重新上传"
        if isinstance(e, FileNotFoundError):
            return "文件不存在或已被移动，请重新上传"
        return f"PDF 解析失败：{e}"

    def _split_sections(self, raw_text: str) -> List[ContractSection]:
        """按标题模式切分章节

        标题行计入所属 section 的内容，避免「标题紧接标题、中间无正文」时
        section 因内容为空而被整体丢弃。
        """
        lines = raw_text.split("\n")
        sections: List[ContractSection] = []
        current_title = "合同正文"
        current_level = SectionLevel.TOP
        current_lines: List[str] = []
        char_offset = 0

        def flush() -> None:
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

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            matched_level = None
            for pattern, level in TITLE_PATTERNS:
                if re.match(pattern, stripped):
                    matched_level = level
                    break

            if matched_level is not None:
                flush()
                current_title = stripped[:60]
                current_level = matched_level
                current_lines = [line]
            else:
                current_lines.append(line)

        flush()

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

"""图片扫描件解析器 — 多模态大模型（VLM）识别

不做本地 OCR，直接把图片交给多模态模型逐字转录：
- 配置见 backend/.env 的 VISION_MODEL / VISION_API_KEY / VISION_BASE_URL
- VISION_API_KEY、VISION_BASE_URL 留空时继承 LLM_API_KEY / LLM_BASE_URL
- 优点：无需安装 300MB+ 的 OCR 运行时，对拍照倾斜、表格、印章干扰更鲁棒

识别结果按空行切分为章节，保持「标题 → 条款」的可读层级。
"""
from __future__ import annotations

import re
from typing import List

from app.llm.vision import get_vision_extractor
from app.parsers.base import (
    ContractParser,
    StructuredContract,
    ContractSection,
    SectionLevel,
    detect_chinese_ratio,
)

# 模型明确表示图里没字时使用的哨兵
NO_TEXT_MARK = "[NO_TEXT]"


class ImageParser(ContractParser):
    SUPPORTED_EXTENSIONS = {"png", "jpg", "jpeg"}

    async def parse(self, file_path: str) -> StructuredContract:
        extractor, reason = get_vision_extractor()
        if extractor is None:
            return StructuredContract(raw_text="", parse_errors=[reason])

        try:
            with open(file_path, "rb") as f:
                image_bytes = f.read()
        except OSError as e:
            return StructuredContract(raw_text="", parse_errors=[f"读取图片失败：{e}"])

        try:
            raw_text = await extractor.extract_text(image_bytes)
        except Exception as e:
            return StructuredContract(
                raw_text="", parse_errors=[f"多模态识别失败：{e}"]
            )

        raw_text = (raw_text or "").strip()
        if not raw_text or NO_TEXT_MARK in raw_text:
            return StructuredContract(
                raw_text="",
                parse_errors=[
                    "未从图片中识别出有效文字。建议重新拍照——保持画面平整、光线充足、"
                    "文字水平且清晰，或改用扫描件 / PDF 上传"
                ],
            )

        chinese_ratio = detect_chinese_ratio(raw_text)
        language = "zh-CN" if chinese_ratio > 0.3 else "unknown"

        return StructuredContract(
            raw_text=raw_text,
            sections=self._split_sections(raw_text),
            word_count=len(raw_text),
            language=language,
            parse_errors=[],
        )

    @staticmethod
    def _split_sections(text: str) -> List[ContractSection]:
        """按空行分段，每段作为一个章节；title 取段首行（截断）"""
        blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
        if not blocks:
            return [ContractSection(
                title="识别全文", level=SectionLevel.TOP,
                content=text, char_start=0, char_end=len(text),
            )]

        sections: List[ContractSection] = []
        cursor = 0
        for block in blocks:
            start = text.find(block, cursor)
            if start < 0:
                start = cursor
            end = start + len(block)
            cursor = end

            first_line = block.splitlines()[0].strip()
            title = first_line if len(first_line) <= 40 else first_line[:40]
            # 「第X条 / 一、/ 1.」开头的段落视为顶级条款，其余按子级
            level = SectionLevel.TOP if re.match(r"^(第[一二三四五六七八九十百]+条|[一二三四五六七八九十]+、|\d+[.、])", first_line) else SectionLevel.SUB
            sections.append(ContractSection(
                title=title or "识别段落",
                level=level,
                content=block,
                char_start=start,
                char_end=end,
            ))
        return sections

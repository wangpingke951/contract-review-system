"""图片扫描件解析器 — PaddleOCR

Phase 4 骨架实现：先加载 PaddleOCR，MVP 阶段如果用户没装 PaddleOCR 也能 graceful fallback
PaddleOCR 安装较重（CPU 版约 300MB，GPU 版更大），可以在需要时 pip install paddleocr paddlepaddle
"""
from __future__ import annotations

from typing import List
from app.parsers.base import (
    ContractParser,
    StructuredContract,
    ContractSection,
    SectionLevel,
    detect_chinese_ratio,
)


class ImageParser(ContractParser):
    SUPPORTED_EXTENSIONS = {"png", "jpg", "jpeg"}

    async def parse(self, file_path: str) -> StructuredContract:
        # OCR 组件是可选依赖，缺失时给出明确指引而不是抛栈
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            return StructuredContract(
                raw_text="",
                parse_errors=[
                    "该文件需要 OCR 识别，当前环境未安装 OCR 组件（PaddleOCR）。"
                    "请安装后重试（pip install paddleocr paddlepaddle），"
                    "或改用 PDF / Word 格式上传"
                ],
            )

        try:
            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            result = ocr.ocr(file_path, cls=True)
            lines: List[str] = []
            for page in result or []:
                if not page:
                    continue
                for item in page:
                    text = item[1][0]  # item = [bbox, (text, confidence)]
                    lines.append(text)
            raw_text = "\n".join(lines)
        except Exception as e:
            return StructuredContract(
                raw_text="", parse_errors=[f"图片识别失败：{e}"]
            )

        # OCR 跑通但没识别出文字：通常是图片质量问题
        if not raw_text.strip():
            return StructuredContract(
                raw_text="",
                parse_errors=[
                    "未从图片中识别出文字。建议重新拍照——保持画面平整、光线充足、"
                    "文字水平且清晰，或改用扫描件上传"
                ],
            )

        chinese_ratio = detect_chinese_ratio(raw_text)
        language = "zh-CN" if chinese_ratio > 0.3 else "unknown"

        # OCR 结果不做复杂切分（扫描件结构不明显），整个作为一个 section
        sections = [ContractSection(
            title="OCR 识别全文",
            level=SectionLevel.TOP,
            content=raw_text,
            char_start=0,
            char_end=len(raw_text),
        )]

        return StructuredContract(
            raw_text=raw_text,
            sections=sections,
            word_count=len(raw_text),
            language=language,
            parse_errors=[],
        )

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
        errors: List[str] = []
        raw_text = ""

        try:
            from paddleocr import PaddleOCR
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
        except ImportError:
            errors.append("PaddleOCR 未安装，请先执行: pip install paddleocr paddlepaddle")
        except Exception as e:
            errors.append(f"图片 OCR 失败: {e}")

        chinese_ratio = detect_chinese_ratio(raw_text) if raw_text else 0
        language = "zh-CN" if chinese_ratio > 0.3 else "unknown"

        # OCR 结果不做复杂切分（扫描件结构不明显），整个作为一个 section
        sections = []
        if raw_text:
            sections.append(ContractSection(
                title="OCR 识别全文",
                level=SectionLevel.TOP,
                content=raw_text,
                char_start=0,
                char_end=len(raw_text),
            ))

        return StructuredContract(
            raw_text=raw_text,
            sections=sections,
            word_count=len(raw_text),
            language=language,
            parse_errors=errors,
        )

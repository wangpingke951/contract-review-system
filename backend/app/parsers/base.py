"""
app/parsers/base.py — 合同解析器抽象基类

三种实现：PDFParser / DocxParser / ImageParser
工厂方法根据文件扩展名自动选择
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List
from enum import Enum


class SectionLevel(int, Enum):
    """章节层级"""
    TOP = 1       # 顶级章节，如 "第一条"、"一、"、"1."
    SUB = 2       # 子章节，如 "1.1"、"（一）"
    DETAIL = 3    # 更细分，如 "a."、"（1）"


@dataclass
class ContractSection:
    """结构化章节"""
    title: str
    level: SectionLevel
    content: str
    char_start: int = 0
    char_end: int = 0


@dataclass
class StructuredContract:
    """解析后的统一输出格式"""
    raw_text: str
    sections: List[ContractSection] = field(default_factory=list)
    word_count: int = 0
    language: str = "zh-CN"
    parse_errors: List[str] = field(default_factory=list)


class ContractParser(ABC):
    """所有解析器的抽象基类"""

    SUPPORTED_EXTENSIONS: set = set()

    @classmethod
    def supports(cls, filename: str) -> bool:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in cls.SUPPORTED_EXTENSIONS

    @abstractmethod
    async def parse(self, file_path: str) -> StructuredContract:
        """从文件路径解析 → StructuredContract"""
        ...


def detect_chinese_ratio(text: str) -> float:
    """粗略估算中文字符占比，用于判断是否中文合同"""
    if not text:
        return 0.0
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return chinese / len(text)

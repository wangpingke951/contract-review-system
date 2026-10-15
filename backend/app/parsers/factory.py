"""Parser 工厂 — 根据扩展名自动选择解析器"""
from app.parsers.base import ContractParser
from app.parsers.pdf_parser import PDFParser
from app.parsers.docx_parser import DocxParser
from app.parsers.image_parser import ImageParser


# 所有已注册的解析器
_ALL_PARSERS: list[type[ContractParser]] = [
    PDFParser,
    DocxParser,
    ImageParser,
]


def get_parser(filename: str) -> ContractParser:
    """
    根据文件名选择对应解析器实例
    不支持的扩展名抛 ValueError
    """
    for parser_cls in _ALL_PARSERS:
        if parser_cls.supports(filename):
            return parser_cls()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "(无扩展名)"
    raise ValueError(f"不支持的文件类型: .{ext}")


def supported_extensions() -> set[str]:
    ext: set[str] = set()
    for cls in _ALL_PARSERS:
        ext |= cls.SUPPORTED_EXTENSIONS
    return ext

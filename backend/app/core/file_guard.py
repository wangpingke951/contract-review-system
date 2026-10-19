"""
app/core/file_guard.py — 上传文件真实类型校验

只校验扩展名不够：把 .exe 改名成 .docx 一样能塞进来。
这里读文件头（magic number）判断真实类型，与声明的扩展名比对。

支持的判定：
- pdf  : %PDF
- docx : ZIP 容器（PK\\x03\\x04），且解包后含 word/document.xml
- png  : \\x89PNG\\r\\n\\x1a\\n
- jpg  : \\xff\\xd8\\xff
- txt/md : 无固定魔数，只做「可解码为文本」的宽松校验
"""
from __future__ import annotations

import zipfile

from app.core.exceptions import ValidationError

_IMAGE_MAGIC = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
}


def _looks_like_text(path: str) -> bool:
    """读取前 4KB，不能含 NUL 字节（二进制文件的典型特征）"""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return False
    return b"\x00" not in head


def _is_docx(path: str, head: bytes) -> bool:
    if not head.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(path) as zf:
            return any(n.startswith("word/") for n in zf.namelist())
    except (zipfile.BadZipFile, OSError):
        return False


def verify(path: str, ext: str) -> None:
    """
    校验失败抛 ValidationError（面向用户的文案）。
    未知扩展名直接拒绝，避免出现「没校验就放行」的口子。
    """
    ext = (ext or "").lower()
    with open(path, "rb") as f:
        head = f.read(16)

    if ext == "pdf":
        if not head.startswith(b"%PDF"):
            raise ValidationError("文件内容与扩展名不符：这不是有效的 PDF 文件")
        return

    if ext == "docx":
        if not _is_docx(path, head):
            raise ValidationError("文件内容与扩展名不符：这不是有效的 Word(.docx) 文件")
        return

    if ext in _IMAGE_MAGIC:
        if not any(head.startswith(m) for m in _IMAGE_MAGIC[ext]):
            raise ValidationError(f"文件内容与扩展名不符：这不是有效的 {ext.upper()} 图片")
        return

    if ext in ("txt", "md"):
        if not _looks_like_text(path):
            raise ValidationError("文件看起来是二进制内容，不是纯文本文件")
        return

    raise ValidationError(f"不支持的文件类型 .{ext}")

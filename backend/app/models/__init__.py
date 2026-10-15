"""
app/models/__init__.py — 只导出 Base 和 metadata

⚠️ 关键约束：这里绝对不能写 `from . import *` 或聚合导入各 model。
原因：如果聚合导入的某个 model 文件有语法错误或 import 不存在的模块，
会导致整个模块在 import 阶段就崩溃（ImportError 链）。
每个 model 文件按需在需要的地方单独 import。

Base.metadata 用于 Alembic 迁移和 create_all() 建表。
"""
from app.core.database import Base

__all__ = ["Base"]

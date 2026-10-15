"""tests/helpers.py — 测试脚本共享工具"""
import os

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(TESTS_DIR, "..")
ROOT_DIR = os.path.join(TESTS_DIR, "..", "..")


def backend_on_path():
    """把 backend 目录加入 sys.path（便于 from app.xxx import ...）"""
    import sys
    if BACKEND_DIR not in sys.path:
        sys.path.insert(0, BACKEND_DIR)


def _asset(name: str) -> str:
    """项目根目录下的测试素材绝对路径"""
    return os.path.join(ROOT_DIR, name)

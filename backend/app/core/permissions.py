"""
app/core/permissions.py — 细粒度权限目录

设计取舍：
- 角色（role）保持 user / admin 两级不变，不做角色膨胀
- 普通用户的额外能力用「权限点」授予，管理员恒拥有全部权限点
- 权限点固定枚举，不接受任意字符串，避免前后端各写一套对不上
- **模型配置（含 API Key）不在可授权范围内**，始终 admin 独占

权限点按「模块:动作」命名，前端菜单/路由与后端依赖共用同一份 key。
"""
from __future__ import annotations

from typing import Iterable

from app.core.security import UserRole

# 权限目录：新增权限点只需在这里加一条，前后端自动同步
PERMISSIONS: list[dict] = [
    {
        "key": "knowledge:manage",
        "label": "知识库管理",
        "desc": "上传/替换/删除知识文档，维护风险类别",
    },
    {
        "key": "template:manage",
        "label": "审查模板",
        "desc": "创建/修改/删除审查模板",
    },
    {
        "key": "stats:view",
        "label": "用量统计",
        "desc": "查看 LLM 调用次数、token 与耗时",
    },
    {
        "key": "audit:view",
        "label": "审计日志",
        "desc": "查看全站操作审计记录",
    },
    {
        "key": "user:manage",
        "label": "用户与权限",
        "desc": "查看用户列表、授予权限、禁用账号、重置密码",
    },
]

ALL_PERMISSION_KEYS: list[str] = [p["key"] for p in PERMISSIONS]
_PERMISSION_SET = set(ALL_PERMISSION_KEYS)
_LABELS = {p["key"]: p["label"] for p in PERMISSIONS}


def parse_permissions(raw: str | None) -> set[str]:
    """把 '' / 'a,b' 解析成合法权限集合（未知权限点直接丢弃）"""
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip() in _PERMISSION_SET}


def dump_permissions(keys: Iterable[str]) -> str:
    """校验并序列化为逗号分隔字符串（保持目录顺序，便于比对）"""
    wanted = set(keys or [])
    unknown = wanted - _PERMISSION_SET
    if unknown:
        raise ValueError(f"未知权限点: {sorted(unknown)}")
    return ",".join(k for k in ALL_PERMISSION_KEYS if k in wanted)


def effective_permissions(role: UserRole, raw: str | None) -> set[str]:
    """管理员恒为全部权限；普通用户按授予情况"""
    if role == UserRole.ADMIN:
        return set(ALL_PERMISSION_KEYS)
    return parse_permissions(raw)


def permission_label(key: str) -> str:
    return _LABELS.get(key, key)

"""app/schemas/model_config.py — 模型配置 Pydantic 模型"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ModelConfigOut(BaseModel):
    llm_provider: str = ""
    llm_api_key: str = ""          # 掩码
    llm_key_set: bool = False
    llm_model: str = ""
    llm_base_url: str = ""

    vision_model: str = ""
    vision_api_key: str = ""
    vision_key_set: bool = False
    vision_base_url: str = ""

    source: str = "env"            # db | env
    updated_at: Optional[datetime] = None


class ModelConfigIn(BaseModel):
    """密钥留空或传掩码表示不修改；传 "-" 表示清空"""
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None

    vision_model: Optional[str] = None
    vision_api_key: Optional[str] = None
    vision_base_url: Optional[str] = None


class ConnectionTestIn(BaseModel):
    provider: str
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    kind: str = "llm"              # llm | vision


class ConnectionTestOut(BaseModel):
    ok: bool
    latency_ms: int = 0
    reply: Optional[str] = None
    error: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None

"""app/schemas/contract.py — 合同相关 Pydantic 模型"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ContractSectionOut(BaseModel):
    title: str
    level: int
    content: str
    char_start: int = 0
    char_end: int = 0


class ContractUploadResponse(BaseModel):
    """上传 + 解析后的返回"""
    id: int
    filename: str
    file_type: str
    status: str
    word_count: int = 0
    language: str = "zh-CN"
    sections: List[ContractSectionOut] = Field(default_factory=list)
    parse_errors: List[str] = Field(default_factory=list)
    # 面向用户的失败原因（成功时为 None）
    parse_error: Optional[str] = None


class ContractListItem(BaseModel):
    """列表项（不含完整 parsed_content 以减少响应体积）"""
    id: int
    filename: str
    file_type: str
    status: str
    created_at: datetime
    parse_error: Optional[str] = None


class ContractListResponse(BaseModel):
    items: List[ContractListItem]
    total: int


class ContractDetailResponse(BaseModel):
    """合同详情（用于预览结构化内容）"""
    id: int
    filename: str
    file_type: str
    status: str
    parsed_content: Optional[str] = None
    parsed_sections: Optional[List[dict]] = None
    parse_error: Optional[str] = None
    created_at: datetime
    uploader_id: int

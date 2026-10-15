"""app/schemas/assistant.py — 法律问答会话的请求/响应模型"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class SessionCreateIn(BaseModel):
    title: str | None = None


class SessionOut(BaseModel):
    id: int
    title: str
    message_count: int = 0
    created_at: datetime
    last_active_at: datetime


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime


class QuestionIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class QuestionOut(BaseModel):
    answer: str

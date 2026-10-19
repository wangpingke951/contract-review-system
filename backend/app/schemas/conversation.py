"""app/schemas/conversation.py — 对话 Pydantic 模型"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class ConversationOut(BaseModel):
    id: int
    review_id: int


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime


class QuestionIn(BaseModel):
    content: str


class QuestionOut(BaseModel):
    answer: str
    citations: list[dict] = []

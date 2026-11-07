"""对话出入参。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ChatSessionOut(BaseModel):
    id: UUID
    created_at: datetime

    model_config = {
        "from_attributes": True,  # 支持从 ORM 模型直接转 Schema
    }


# 引用结构固定五字段（SERVER_SPEC 阶段 3）
class CitationOut(BaseModel):
    doc_id: UUID
    doc_title: str
    chunk_id: UUID
    location: dict | None = None
    snippet: str


class ChatMessageOut(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    refused: bool
    citations: list[CitationOut] | None = None
    created_at: datetime

    model_config = {
        "from_attributes": True,  # 支持从 ORM 模型直接转 Schema
    }
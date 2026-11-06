"""对话会话、消息与调用日志表（ai_ext）。

会话归属用户；消息挂会话；调用日志只记录每次回答的元信息，
不保存正文与密钥（SERVER_SPEC 阶段 3 领域模型）。
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 消息角色常量（业务代码只认这两个字符串）
CHAT_ROLE_USER = "user"
CHAT_ROLE_ASSISTANT = "assistant"


class ChatSession(Base):
    __tablename__ = "chat_session"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 会话归属用户；AI 表可以 FK 到 system 表，反向禁止
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_session.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 仅助手消息：拒答标记；普通回答为 false
    refused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 仅助手消息：引用列表，元素固定 {doc_id, doc_title, chunk_id, location, snippet}
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ChatCallLog(Base):
    __tablename__ = "chat_call_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_session.id"),
        nullable=False,
        index=True,
    )
    # 模型名（来自配置，不写死具体值）
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    # 单次回答耗时（毫秒）
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # 检索命中的 chunk_id 列表（JSONB 字符串数组）；闲聊/拒答为空
    chunk_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    refused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
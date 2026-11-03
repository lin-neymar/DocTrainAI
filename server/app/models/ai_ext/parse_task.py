"""文档解析任务表（ai_ext）。

状态机：pending → running → succeeded | failed。
失败时写入 error_summary。不把解析状态写进 doc 主表。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 实现：任务状态常量（业务代码只认这些字符串，不写角色判断）
PARSE_STATUS_PENDING = "pending"
PARSE_STATUS_RUNNING = "running"
PARSE_STATUS_SUCCEEDED = "succeeded"
PARSE_STATUS_FAILED = "failed"


class DocParseTask(Base):
    __tablename__ = "doc_parse_task"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # 关联底座文档；AI 表可以 FK 到 system 表，反向禁止
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doc.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PARSE_STATUS_PENDING,
    )
    # 失败摘要；成功保持 NULL
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

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
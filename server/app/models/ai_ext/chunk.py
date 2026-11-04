"""文档分片表（ai_ext）。
检索单位：正文 + 向量 + 全文。维度必须等于配置 EMBEDDING_DIM。
全文：业务写入前用 jieba 分词，再 to_tsvector('simple', ...)。
"""

import uuid  # 生成UUID主键
from datetime import datetime  # 日期时间类型
from typing import Any  # 任意类型注解

from pgvector.sqlalchemy import Vector  # pgvector向量字段，存储embedding
from sqlalchemy import DateTime, ForeignKey, Integer, Text, func  # 基础字段与数据库函数
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID  # Postgres专属扩展类型
from sqlalchemy.orm import Mapped, mapped_column  # SQLAlchemy2.0 ORM映射注解

from app.config import settings  # 全局配置
from app.database import Base  # ORM基类，所有模型继承它


class DocChunk(Base):
    __tablename__ = "doc_chunk"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doc.id"),
        nullable=False,
        index=True,
    )
    # 同一文档内顺序（0,1,2…），便于引用与调试
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 例：{"ext":"md","heading":"年假天数"} 或 {"ext":"pdf","page":3}
    location: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # 向量列：维数与 settings.embedding_dim 一致（当前默认 1024）
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim),
        nullable=True,
    )

    # 全文向量；解析成功写入前可为 NULL
    content_tsv: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
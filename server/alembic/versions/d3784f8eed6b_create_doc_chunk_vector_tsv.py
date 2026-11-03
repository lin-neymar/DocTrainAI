"""create_doc_chunk_vector_tsv

Revision ID: d3784f8eed6b
Revises: de66328ad70b
Create Date: 2026-11-03 16:47:55.271984

S2：分片表 doc_chunk；启用 pgvector；全文 content_tsv + GIN。
向量维数取自 settings.embedding_dim（须与 EMBEDDING_MODEL 一致；换维另开迁移）。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op
from app.config import settings

# revision identifiers, used by Alembic.
revision: str = "d3784f8eed6b"
down_revision: Union[str, Sequence[str], None] = "de66328ad70b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 实现：库级启用 pgvector（镜像已含扩展文件，此处只 CREATE EXTENSION）
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "doc_chunk",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("doc_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "location",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "embedding",
            Vector(dim=settings.embedding_dim),
            nullable=True,
        ),
        sa.Column("content_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["doc_id"], ["doc.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doc_chunk_doc_id", "doc_chunk", ["doc_id"])
    # 实现：全文检索 GIN；向量 ANN 索引数据量大后再加
    op.create_index(
        "ix_doc_chunk_content_tsv",
        "doc_chunk",
        ["content_tsv"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_doc_chunk_content_tsv", table_name="doc_chunk")
    op.drop_index("ix_doc_chunk_doc_id", table_name="doc_chunk")
    op.drop_table("doc_chunk")
    # 不 drop extension vector（可能被其它对象依赖）

"""create_chat_tables

Revision ID: e2a1f3b4c5d6
Revises: 11092dcb54d3
Create Date: 2026-11-06

S3：会话 chat_session、消息 chat_message、调用日志 chat_call_log。
引用与 chunk_ids 用 JSONB；日志不保存正文与密钥。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2a1f3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "11092dcb54d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_session",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_session_user_id", "chat_session", ["user_id"])

    op.create_table(
        "chat_message",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("refused", sa.Boolean(), nullable=False),
        sa.Column(
            "citations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["chat_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_message_session_id", "chat_message", ["session_id"])

    op.create_table(
        "chat_call_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "chunk_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("refused", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["chat_session.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_call_log_session_id", "chat_call_log", ["session_id"])
    op.create_index("ix_chat_call_log_user_id", "chat_call_log", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_call_log_user_id", table_name="chat_call_log")
    op.drop_index("ix_chat_call_log_session_id", table_name="chat_call_log")
    op.drop_table("chat_call_log")
    op.drop_index("ix_chat_message_session_id", table_name="chat_message")
    op.drop_table("chat_message")
    op.drop_index("ix_chat_session_user_id", table_name="chat_session")
    op.drop_table("chat_session")
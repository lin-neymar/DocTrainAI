"""create dept table

Revision ID: a9d622a793ad
Revises:
Create Date: 2026-10-28

G5 迁移脚本说明：
  - upgrade()：在 PostgreSQL 里 CREATE TABLE dept
  - downgrade()：回滚时 DROP TABLE dept
  - 此文件由 Alembic 管理，禁止用手写 SQL 直接改生产库结构
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a9d622a793ad"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dept",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["parent_id"], ["dept.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("dept")

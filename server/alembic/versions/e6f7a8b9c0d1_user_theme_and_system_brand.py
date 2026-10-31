"""user theme_primary + system_brand table

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-10-31

S1：个人主题色列 + 全局品牌表（供 seed 写入 T2/T3 默认值）。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("theme_primary", sa.String(length=16), nullable=True),
    )
    op.create_table(
        "system_brand",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("site_name", sa.String(length=128), nullable=False),
        sa.Column("login_subtitle", sa.String(length=256), nullable=False),
        sa.Column("logo_storage_key", sa.String(length=512), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("system_brand")
    op.drop_column("user", "theme_primary")

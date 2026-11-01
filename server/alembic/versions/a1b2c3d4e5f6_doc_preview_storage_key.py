"""doc.preview_storage_key

Revision ID: a1b2c3d4e5f6
Revises: f8a9b0c1d2e3
Create Date: 2026-11-01

D2：预览件存储键（office 转 PDF 等）；可空。非解析状态字段。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "doc",
        sa.Column("preview_storage_key", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("doc", "preview_storage_key")

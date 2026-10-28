"""create doc course and course_doc tables

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-10-28

B3 + B4：文档元数据、培训课程、课程-文档关联（阶段 1 底座表最后一组）。
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doc",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("dept_id", sa.UUID(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("extension", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["dept_id"], ["dept.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doc_dept_id", "doc", ["dept_id"], unique=False)

    op.create_table(
        "course",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dept_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["dept_id"], ["dept.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_course_dept_id", "course", ["dept_id"], unique=False)

    op.create_table(
        "course_doc",
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("doc_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["course.id"]),
        sa.ForeignKeyConstraint(["doc_id"], ["doc.id"]),
        sa.PrimaryKeyConstraint("course_id", "doc_id"),
    )


def downgrade() -> None:
    op.drop_table("course_doc")
    op.drop_index("ix_course_dept_id", table_name="course")
    op.drop_table("course")
    op.drop_index("ix_doc_dept_id", table_name="doc")
    op.drop_table("doc")

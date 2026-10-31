"""doc_audience_dept + course_audience_dept

Revision ID: f8a9b0c1d2e3
Revises: e6f7a8b9c0d1
Create Date: 2026-10-31

S4：方案 B 可见组织关联表；旧数据 audience 初始 = 原归属 dept_id。
本迁移不改 get_visible_doc_ids（S5）。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doc_audience_dept",
        sa.Column("doc_id", sa.UUID(), nullable=False),
        sa.Column("dept_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["doc_id"], ["doc.id"]),
        sa.ForeignKeyConstraint(["dept_id"], ["dept.id"]),
        sa.PrimaryKeyConstraint("doc_id", "dept_id"),
    )
    op.create_index(
        "ix_doc_audience_dept_dept_id",
        "doc_audience_dept",
        ["dept_id"],
        unique=False,
    )

    op.create_table(
        "course_audience_dept",
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("dept_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["course.id"]),
        sa.ForeignKeyConstraint(["dept_id"], ["dept.id"]),
        sa.PrimaryKeyConstraint("course_id", "dept_id"),
    )
    op.create_index(
        "ix_course_audience_dept_dept_id",
        "course_audience_dept",
        ["dept_id"],
        unique=False,
    )

    # 实现：旧文档/课程 audience 初始等于归属部门（含已软删行，避免日后恢复缺行）
    op.execute(
        sa.text(
            "INSERT INTO doc_audience_dept (doc_id, dept_id) "
            "SELECT id, dept_id FROM doc"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO course_audience_dept (course_id, dept_id) "
            "SELECT id, dept_id FROM course"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_course_audience_dept_dept_id", table_name="course_audience_dept")
    op.drop_table("course_audience_dept")
    op.drop_index("ix_doc_audience_dept_dept_id", table_name="doc_audience_dept")
    op.drop_table("doc_audience_dept")

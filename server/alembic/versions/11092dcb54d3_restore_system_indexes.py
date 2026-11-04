"""restore_system_indexes

Revision ID: 11092dcb54d3
Revises: d3784f8eed6b
Create Date: 2026-11-04 14:12:25.273677

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '11092dcb54d3'
down_revision: Union[str, Sequence[str], None] = 'd3784f8eed6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 恢复 de66328ad70b 误删的底座索引（PROJECT_SPEC MUST 13：未删除时唯一）。
    # 部分唯一索引：用户名 / 角色 code / 权限 code 在 is_deleted=false 时唯一
    op.create_index(
        "uq_user_username_not_deleted",
        "user",
        ["username"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "uq_role_code_not_deleted",
        "role",
        ["code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "uq_permission_code_not_deleted",
        "permission",
        ["code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    # 普通外键索引：部门归属与可见组织查询
    op.create_index("ix_user_dept_id", "user", ["dept_id"], unique=False)
    op.create_index("ix_doc_dept_id", "doc", ["dept_id"], unique=False)
    op.create_index(
        "ix_doc_audience_dept_dept_id", "doc_audience_dept", ["dept_id"], unique=False
    )
    op.create_index("ix_course_dept_id", "course", ["dept_id"], unique=False)
    op.create_index(
        "ix_course_audience_dept_dept_id",
        "course_audience_dept",
        ["dept_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("uq_user_username_not_deleted", table_name="user")
    op.drop_index("uq_role_code_not_deleted", table_name="role")
    op.drop_index("uq_permission_code_not_deleted", table_name="permission")
    op.drop_index("ix_user_dept_id", table_name="user")
    op.drop_index("ix_doc_dept_id", table_name="doc")
    op.drop_index("ix_doc_audience_dept_dept_id", table_name="doc_audience_dept")
    op.drop_index("ix_course_dept_id", table_name="course")
    op.drop_index("ix_course_audience_dept_dept_id", table_name="course_audience_dept")

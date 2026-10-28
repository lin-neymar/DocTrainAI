"""create user and user_role tables

Revision ID: c4d5e6f7a8b9
Revises: b3c8f1e2a4d5
Create Date: 2026-10-28

B2：用户归属单一部门；与角色多对多。密码哈希列仅存储，登录逻辑在阶段 D。
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c8f1e2a4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
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
    op.create_index(
        "uq_user_username_not_deleted",
        "user",
        ["username"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index("ix_user_dept_id", "user", ["dept_id"], unique=False)

    op.create_table(
        "user_role",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )


def downgrade() -> None:
    op.drop_table("user_role")
    op.drop_index("ix_user_dept_id", table_name="user")
    op.drop_index("uq_user_username_not_deleted", table_name="user")
    op.drop_table("user")

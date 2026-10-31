"""用户表 ORM（user）与用户-角色关联（user_role）。

阶段 1：每人恰好一个 dept_id；密码只存 bcrypt 哈希（登录/D 切片再写校验逻辑）。
软删除后业务层禁止登录；用户名在未删除记录中唯一（迁移里 partial unique）。
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    # bcrypt 哈希约 60 字符；留余量，禁止在 API 响应里返回此字段
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    dept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dept.id"),
        nullable=False,
    )

    # T1：个人主题主色（如 #1F4B7A）；空则前端用默认色
    theme_primary: Mapped[str | None] = mapped_column(String(16), nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserRole(Base):
    """用户 ↔ 角色 多对多；登录后合并各角色的 permission 得到权限码集合。"""

    __tablename__ = "user_role"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id"),
        primary_key=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("role.id"),
        primary_key=True,
    )

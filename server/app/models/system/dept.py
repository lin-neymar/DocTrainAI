"""G5：部门表 ORM（对应 PostgreSQL 里的 dept 表）。

业务含义（SERVER_SPEC）：
  - 公司是单租户，部门是一棵组织树；
  - parent_id 为空 → 根部门（如「总公司」）；
  - parent_id 指向另一行 dept.id → 下级部门；
  - is_deleted=True → 软删除，行还在，业务查询默认过滤掉。

和 TypeScript 类比：这个 class 像「表结构的 TypeScript 接口 + 默认值」，不是 Pydantic 的 API 入参。
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Dept(Base):
    """部门实体。表名 dept，不要用 SQL 保留字做表名时这里显式指定 __tablename__。"""

    __tablename__ = "dept"

    # 主键：项目规约统一 UUID，不用自增整数（方便分布式、合并数据）
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,  # Python 侧插入时可自动生成 id
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # 自关联外键：同一张表，parent_id 指向父部门的 id；根部门为 NULL
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dept.id"),
        nullable=True,
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # timestamptz：带时区，与 PROJECT_SPEC 一致；server_default 让数据库填创建时间
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

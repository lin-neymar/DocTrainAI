"""培训课程表 ORM（course）、课程-文档关联（course_doc）、可见组织（course_audience_dept）。

课程归属部门；与文档多对多。删课程不删文档；挂接不改变文档可见性。
阅读规则与文档同构（course:read + audience 子树），算法在 S5 落地。
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Course(Base):
    __tablename__ = "course"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    # 可选简介，管理端展示；不参与权限与检索
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 归属部门；阅读可见另见 CourseAudienceDept
    dept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dept.id"),
        nullable=False,
    )

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


class CourseDoc(Base):
    """课程 ↔ 文档 多对多；PUT /courses/{id}/docs 整表替换本表该 course 的行。"""

    __tablename__ = "course_doc"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course.id"),
        primary_key=True,
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doc.id"),
        primary_key=True,
    )


class CourseAudienceDept(Base):
    """课程 ↔ 可见组织节点；选中节点表示其部门子树内人员可读（方案 B）。"""

    __tablename__ = "course_audience_dept"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course.id"),
        primary_key=True,
    )
    dept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dept.id"),
        primary_key=True,
    )

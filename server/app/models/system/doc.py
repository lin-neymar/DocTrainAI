"""制度文档元数据表 ORM（doc）与可见组织关联（doc_audience_dept）。

阶段 1 只存身份与文件元数据 + 磁盘上的原文件（storage_key）；不存正文、解析状态、向量。
dept_id = 归属部门；doc_audience_dept 的每行 dept_id = 可见组织节点（该节点子树可读）。
阅读可见由 get_visible_doc_ids（audience 子树）决定；与是否挂到课程无关。
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Doc(Base):
    __tablename__ = "doc"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    # 归属部门（管理落点）；阅读可见另见 DocAudienceDept
    dept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dept.id"),
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 相对 FILE_STORAGE_DIR 的存储路径/键，由上传 service 生成
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id"),
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


class DocAudienceDept(Base):
    """文档 ↔ 可见组织节点；选中节点表示其部门子树内人员可读（方案 B）。"""

    __tablename__ = "doc_audience_dept"

    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doc.id"),
        primary_key=True,
    )
    dept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dept.id"),
        primary_key=True,
    )

"""系统品牌表（全局一行）：T2 显示名、T3 登录副文案、T4 Logo 存储键。

主题色 T1 在 user.theme_primary，不在本表。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SystemBrand(Base):
    __tablename__ = "system_brand"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    site_name: Mapped[str] = mapped_column(String(128), nullable=False)
    login_subtitle: Mapped[str] = mapped_column(String(256), nullable=False)
    # 相对 FILE_STORAGE_DIR；空表示尚未上传 Logo
    logo_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

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

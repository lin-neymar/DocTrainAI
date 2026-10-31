"""系统品牌（T2/T3/T4）：全局一行读写与 Logo 上传。"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.system.system_brand import SystemBrand
from app.services.system import auth_service
from app.utils.files import resolve_stored_path

# 与 seed_data 默认文案保持一致；业务不 import scripts
_DEFAULT_SITE_NAME = "DocTrainAI"
_DEFAULT_LOGIN_SUBTITLE = "企业内部规章培训与知识助手"

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_LOGO_EXTS = frozenset({"png", "jpg", "jpeg", "webp"})
_LOGO_MAX_BYTES = 2 * 1024 * 1024
_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
_WEBP_RIFF = b"RIFF"
_WEBP_WEBP = b"WEBP"


# 实现：取或创建全局品牌行
def get_or_create_brand(session: Session) -> SystemBrand:
    brand = session.scalar(select(SystemBrand).limit(1))
    if brand is None:
        brand = SystemBrand(
            site_name=_DEFAULT_SITE_NAME,
            login_subtitle=_DEFAULT_LOGIN_SUBTITLE,
            logo_storage_key=None,
        )
        session.add(brand)
        session.commit()
        session.refresh(brand)
    return brand


# 实现：公开/设置页共用的品牌字典
def brand_to_dict(brand: SystemBrand) -> dict:
    return {
        "site_name": brand.site_name,
        "login_subtitle": brand.login_subtitle,
        "has_logo": bool(brand.logo_storage_key),
    }


# 实现：更新显示名与副文案
def update_brand(session: Session, *, site_name: str, login_subtitle: str) -> dict:
    brand = get_or_create_brand(session)
    brand.site_name = site_name.strip()
    brand.login_subtitle = login_subtitle.strip()
    session.commit()
    session.refresh(brand)
    return brand_to_dict(brand)


# 实现：校验并保存 Logo，替换旧文件键
def upload_logo(session: Session, *, filename: str | None, content: bytes) -> dict:
    if not filename or "." not in filename:
        raise ValidationFailedError("Logo 缺少扩展名")
    ext = filename.rsplit(".", 1)[-1].strip().lower()
    if ext not in _LOGO_EXTS:
        raise ValidationFailedError("Logo 仅支持 png、jpg、webp")
    if len(content) <= 0 or len(content) > _LOGO_MAX_BYTES:
        raise ValidationFailedError("Logo 大小须在 1B–2MB 之间")
    head = content[:16]
    if ext == "png" and not head.startswith(_PNG):
        raise ValidationFailedError("文件内容不是合法 PNG")
    if ext in {"jpg", "jpeg"} and not head.startswith(_JPEG):
        raise ValidationFailedError("文件内容不是合法 JPEG")
    if ext == "webp" and not (
        head.startswith(_WEBP_RIFF) and content[8:12] == _WEBP_WEBP
    ):
        raise ValidationFailedError("文件内容不是合法 WEBP")

    brand = get_or_create_brand(session)
    old_key = brand.logo_storage_key
    storage_key = f"brand/{uuid.uuid4().hex}.{ext}"
    dest = settings.file_storage_path / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.write_bytes(content)
    except OSError as exc:
        dest.unlink(missing_ok=True)
        raise ValidationFailedError("Logo 保存失败") from exc

    brand.logo_storage_key = storage_key
    session.commit()
    session.refresh(brand)

    if old_key and old_key != storage_key:
        try:
            old_path = resolve_stored_path(old_key)
            old_path.unlink(missing_ok=True)
        except Exception:
            pass

    return brand_to_dict(brand)


# 实现：解析 Logo 绝对路径；无 Logo 则 404
def get_logo_path(session: Session) -> tuple[Path, str]:
    brand = get_or_create_brand(session)
    if not brand.logo_storage_key:
        raise NotFoundError("logo not found")
    path = resolve_stored_path(brand.logo_storage_key)
    if not path.is_file():
        raise NotFoundError("logo not found")
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")
    return path, media


# 实现：校验并更新当前用户个人主题色
def update_my_theme(session: Session, user_id: uuid.UUID, theme_primary: str | None) -> str | None:
    user = auth_service.get_active_user_by_id(session, user_id)
    if user is None:
        raise NotFoundError("user not found")
    if theme_primary is None or theme_primary.strip() == "":
        user.theme_primary = None
    else:
        value = theme_primary.strip()
        if not _HEX_COLOR.match(value):
            raise ValidationFailedError("主题色须为 #RRGGBB")
        user.theme_primary = value.lower()
    session.commit()
    session.refresh(user)
    return user.theme_primary

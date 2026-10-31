"""系统品牌与个人主题 HTTP 接口。

- GET /system/brand、/system/brand/logo：公开只读（登录页）
- GET/PUT /system/settings、POST logo：system:read / system:update
- PUT /auth/me/theme：已登录改本人主题（挂在本模块路由，前缀见 main）
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.response import success
from app.database import get_db
from app.models.system.user import User
from app.schemas.system.settings import BrandUpdate, ThemeUpdate
from app.services.system import brand_service

brand_router = APIRouter(prefix="/system", tags=["system"])
theme_router = APIRouter(prefix="/auth", tags=["auth"])


@brand_router.get(
    "/brand",
    summary="公开品牌信息",
    description="登录页读取显示名、副文案、是否有 Logo。不鉴权。",
)
# 实现：返回公开品牌字段
def get_public_brand(db: Annotated[Session, Depends(get_db)]) -> dict:
    brand = brand_service.get_or_create_brand(db)
    return success(brand_service.brand_to_dict(brand))


@brand_router.get(
    "/brand/logo",
    summary="公开 Logo 文件",
    description="无 Logo 时 404。不鉴权。",
)
# 实现：返回 Logo 原图
def get_public_logo(db: Annotated[Session, Depends(get_db)]) -> FileResponse:
    path, media = brand_service.get_logo_path(db)
    return FileResponse(path=path, media_type=media)


@brand_router.get(
    "/settings",
    summary="系统设置（品牌）",
    description="需要 system:read。",
)
# 实现：设置页读取品牌
def get_settings(
    _user: Annotated[User, Depends(require_permission("system:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    brand = brand_service.get_or_create_brand(db)
    return success(brand_service.brand_to_dict(brand))


@brand_router.put(
    "/settings",
    summary="更新系统品牌文案",
    description="更新 T2/T3。需要 system:update。",
)
# 实现：保存显示名与副文案
def put_settings(
    body: BrandUpdate,
    _user: Annotated[User, Depends(require_permission("system:update"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    data = brand_service.update_brand(
        db, site_name=body.site_name, login_subtitle=body.login_subtitle
    )
    return success(data)


@brand_router.post(
    "/settings/logo",
    summary="上传系统 Logo",
    description="T4。需要 system:update。",
)
# 实现：multipart 上传 Logo
async def post_logo(
    _user: Annotated[User, Depends(require_permission("system:update"))],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> dict:
    content = await file.read()
    data = brand_service.upload_logo(db, filename=file.filename, content=content)
    return success(data)


@theme_router.put(
    "/me/theme",
    summary="更新个人主题色",
    description="T1。已登录即可；不要求 system:update。",
)
# 实现：只改当前用户 theme_primary
def put_my_theme(
    body: ThemeUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    value = brand_service.update_my_theme(
        db, current_user.id, body.theme_primary
    )
    return success({"theme_primary": value})

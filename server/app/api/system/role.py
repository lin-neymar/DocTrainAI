"""F3：角色 / 权限 HTTP 接口（均需 role:manage）。

GET /permissions 从 DB 读未删权限码；角色 CRUD + PUT 整体替换权限。
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.response import success
from app.database import get_db
from app.models.system.user import User
from app.schemas.common import page_data
from app.schemas.system.role import RoleCreate, RolePermissionsUpdate, RoleUpdate
from app.services.system import role_service

router = APIRouter(tags=["roles"])


@router.get(
    "/permissions",
    summary="权限码列表",
    description="从数据库返回未删除的权限码。需要 role:manage。",
)
# 实现：列出 DB 中未删权限码
def list_permissions(
    current_user: Annotated[User, Depends(require_permission("role:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(role_service.list_permissions(db))


@router.get(
    "/roles",
    summary="角色列表",
    description="分页列出未删除角色。需要 role:manage。",
)
# 实现：分页列出角色
def list_roles(
    current_user: Annotated[User, Depends(require_permission("role:manage"))],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    items, total = role_service.list_roles(db, page=page, page_size=page_size)
    return success(page_data(items=items, total=total, page=page, page_size=page_size))


@router.get(
    "/roles/{role_id}",
    summary="角色详情",
    description="返回角色及其 permission_codes。需要 role:manage。",
)
# 实现：角色详情
def get_role(
    role_id: UUID,
    current_user: Annotated[User, Depends(require_permission("role:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(role_service.get_role(db, role_id=role_id))


@router.post(
    "/roles",
    summary="创建角色",
    description="创建角色（code/name）。需要 role:manage。",
)
# 实现：创建角色
def create_role(
    body: RoleCreate,
    current_user: Annotated[User, Depends(require_permission("role:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(role_service.create_role(db, code=body.code, name=body.name))


@router.put(
    "/roles/{role_id}",
    summary="更新角色",
    description="可改 code、name。需要 role:manage。",
)
# 实现：更新角色
def update_role(
    role_id: UUID,
    body: RoleUpdate,
    current_user: Annotated[User, Depends(require_permission("role:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(
        role_service.update_role(
            db, role_id=role_id, code=body.code, name=body.name
        )
    )


@router.put(
    "/roles/{role_id}/permissions",
    summary="替换角色权限",
    description="用 permission_codes 整体替换；未知码 404。需要 role:manage。",
)
# 实现：整体替换角色权限码
def replace_role_permissions(
    role_id: UUID,
    body: RolePermissionsUpdate,
    current_user: Annotated[User, Depends(require_permission("role:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(
        role_service.replace_permissions(
            db, role_id=role_id, permission_codes=body.permission_codes
        )
    )


@router.delete(
    "/roles/{role_id}",
    summary="软删除角色",
    description="仍有未删除用户绑定时返回 409。需要 role:manage。",
)
# 实现：软删除角色
def delete_role(
    role_id: UUID,
    current_user: Annotated[User, Depends(require_permission("role:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    role_service.soft_delete_role(db, role_id=role_id)
    return success()

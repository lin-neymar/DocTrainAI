"""用户 HTTP 接口（细粒度权限码，并受数据范围约束）。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.response import success
from app.database import get_db
from app.models.system.user import User
from app.schemas.common import page_data
from app.schemas.system.user import (
    UserBatchDelete,
    UserCreate,
    UserPasswordReset,
    UserUpdate,
)
from app.services.system import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    summary="用户列表",
    description="分页列出数据范围内的用户；可选 username（模糊）。需要 user:read。",
)
# 实现：分页列出可见范围内用户（可选用户名模糊搜索）
def list_users(
    current_user: Annotated[User, Depends(require_permission("user:read"))],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    username: Annotated[str | None, Query(max_length=64)] = None,
) -> dict:
    items, total = user_service.list_users(
        db,
        operator_id=current_user.id,
        page=page,
        page_size=page_size,
        username=username,
    )
    return success(page_data(items=items, total=total, page=page, page_size=page_size))


@router.get(
    "/{user_id}",
    summary="用户详情",
    description="目标用户部门不在范围内时返回 404。需要 user:read。",
)
# 实现：用户详情
def get_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_permission("user:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(
        user_service.get_user(db, operator_id=current_user.id, user_id=user_id)
    )


@router.post(
    "",
    summary="创建用户",
    description="需要 user:create；dept_id 须在操作者数据范围内。",
)
# 实现：创建用户
def create_user(
    body: UserCreate,
    current_user: Annotated[User, Depends(require_permission("user:create"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    data = user_service.create_user(
        db,
        operator_id=current_user.id,
        username=body.username,
        password=body.password,
        dept_id=body.dept_id,
        role_ids=body.role_ids,
    )
    return success(data)


@router.put(
    "/{user_id}",
    summary="更新用户",
    description="可改用户名、部门、角色列表。需要 user:update。",
)
# 实现：更新用户
def update_user(
    user_id: UUID,
    body: UserUpdate,
    current_user: Annotated[User, Depends(require_permission("user:update"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    data = user_service.update_user(
        db,
        operator_id=current_user.id,
        user_id=user_id,
        username=body.username,
        dept_id=body.dept_id,
        role_ids=body.role_ids,
    )
    return success(data)


@router.put(
    "/{user_id}/password",
    summary="重置密码",
    description="管理员重置他人密码。需要 user:reset_password，并受数据范围约束。",
)
# 实现：管理员重置密码
def reset_password(
    user_id: UUID,
    body: UserPasswordReset,
    current_user: Annotated[User, Depends(require_permission("user:reset_password"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user_service.reset_password(
        db,
        operator_id=current_user.id,
        user_id=user_id,
        new_password=body.password,
    )
    return success()


@router.post(
    "/batch-delete",
    summary="批量软删除用户",
    description="需要 user:delete；跳过自己；任一目标越范围则整批不删并 404。",
)
# 实现：批量软删除用户
def batch_delete_users(
    body: UserBatchDelete,
    current_user: Annotated[User, Depends(require_permission("user:delete"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    data = user_service.soft_delete_users(
        db, operator_id=current_user.id, user_ids=body.ids
    )
    return success(data)


@router.delete(
    "/{user_id}",
    summary="软删除用户",
    description="需要 user:delete；不能删除自己。",
)
# 实现：软删除用户
def delete_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_permission("user:delete"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user_service.soft_delete_user(
        db, operator_id=current_user.id, user_id=user_id
    )
    return success()

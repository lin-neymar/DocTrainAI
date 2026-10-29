"""F1：部门 HTTP 接口。

读：已登录即可，结果限制在 get_accessible_dept_ids 内。
写：需要 dept:manage。
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.response import success
from app.database import get_db
from app.models.system.user import User
from app.schemas.common import page_data
from app.schemas.system.dept import DeptCreate, DeptUpdate
from app.services.system import dept_service

router = APIRouter(prefix="/depts", tags=["depts"])


@router.get(
    "",
    summary="部门列表",
    description="分页列出当前用户数据范围内的部门。需要登录。",
)
# 实现：分页列出可见部门
def list_depts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    items, total = dept_service.list_depts(
        db, user_id=current_user.id, page=page, page_size=page_size
    )
    return success(page_data(items=items, total=total, page=page, page_size=page_size))


@router.get(
    "/tree",
    summary="部门树",
    description="返回数据范围内的部门树，便于选择所属部门。需要登录。",
)
# 实现：返回可见部门树
def dept_tree(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(dept_service.get_dept_tree(db, current_user.id))


@router.get(
    "/{dept_id}",
    summary="部门详情",
    description="不在数据范围内时返回 404。需要登录。",
)
# 实现：部门详情（范围外当不存在）
def get_dept(
    dept_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(dept_service.get_dept(db, current_user.id, dept_id))


@router.post(
    "",
    summary="创建部门",
    description="需要 dept:manage。创建根部门还需要 data:scope:all。",
)
# 实现：创建部门
def create_dept(
    body: DeptCreate,
    current_user: Annotated[User, Depends(require_permission("dept:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    data = dept_service.create_dept(
        db,
        user_id=current_user.id,
        name=body.name,
        parent_id=body.parent_id,
    )
    return success(data)


@router.put(
    "/{dept_id}",
    summary="更新部门",
    description="需要 dept:manage。可改名称与父级；禁止成环。",
)
# 实现：更新部门
def update_dept(
    dept_id: UUID,
    body: DeptUpdate,
    current_user: Annotated[User, Depends(require_permission("dept:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    data = dept_service.update_dept(
        db,
        user_id=current_user.id,
        dept_id=dept_id,
        name=body.name,
        parent_id=body.parent_id,
        parent_id_provided="parent_id" in body.model_fields_set,
    )
    return success(data)


@router.delete(
    "/{dept_id}",
    summary="软删除部门",
    description="需要 dept:manage。仍有下级或用户时返回 409。",
)
# 实现：软删除部门
def delete_dept(
    dept_id: UUID,
    current_user: Annotated[User, Depends(require_permission("dept:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    dept_service.soft_delete_dept(db, user_id=current_user.id, dept_id=dept_id)
    return success()

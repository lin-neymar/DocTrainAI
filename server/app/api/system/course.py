"""课程 HTTP 接口。

读：course:read + get_visible_course_ids（audience 子树）。
写：course:create/update/delete（管理范围）；挂文档：course:attach_doc（文档须可见）。
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
from app.schemas.system.course import CourseCreate, CourseDocsUpdate, CourseUpdate
from app.services.system import course_service

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get(
    "",
    summary="课程列表",
    description="分页列出当前用户阅读可见的课程（含 audience_dept_ids）。需要 course:read。",
)
# 实现：分页列出可见范围内课程
def list_courses(
    current_user: Annotated[User, Depends(require_permission("course:read"))],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    items, total = course_service.list_courses(
        db, operator_id=current_user.id, page=page, page_size=page_size
    )
    return success(page_data(items=items, total=total, page=page, page_size=page_size))


@router.get(
    "/{course_id}",
    summary="课程详情",
    description="不在阅读可见集合时 404。需要 course:read。",
)
# 实现：课程详情
def get_course(
    course_id: UUID,
    current_user: Annotated[User, Depends(require_permission("course:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(
        course_service.get_course(
            db, operator_id=current_user.id, course_id=course_id
        )
    )


@router.post(
    "",
    summary="创建课程",
    description=(
        "需要 course:create；可传 audience_dept_ids。"
        "部门官 audience 由服务端固定为本部门。"
    ),
)
# 实现：创建课程
def create_course(
    body: CourseCreate,
    current_user: Annotated[User, Depends(require_permission("course:create"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(
        course_service.create_course(
            db,
            operator_id=current_user.id,
            title=body.title,
            description=body.description,
            dept_id=body.dept_id,
            audience_dept_ids=body.audience_dept_ids,
        )
    )


@router.put(
    "/{course_id}",
    summary="更新课程",
    description="可改 title、description、dept_id、audience_dept_ids。需要 course:update。",
)
# 实现：更新课程元数据与 audience
def update_course(
    course_id: UUID,
    body: CourseUpdate,
    current_user: Annotated[User, Depends(require_permission("course:update"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(
        course_service.update_course(
            db,
            operator_id=current_user.id,
            course_id=course_id,
            title=body.title,
            description=body.description,
            dept_id=body.dept_id,
            fields_set=body.model_fields_set,
            audience_dept_ids=body.audience_dept_ids,
            audience_provided="audience_dept_ids" in body.model_fields_set,
        )
    )


@router.put(
    "/{course_id}/docs",
    summary="替换课程文档",
    description="用 doc_ids 整体替换；文档须对操作者可见。需要 course:attach_doc。",
)
# 实现：整体替换课程挂接文档
def replace_course_docs(
    course_id: UUID,
    body: CourseDocsUpdate,
    current_user: Annotated[User, Depends(require_permission("course:attach_doc"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(
        course_service.replace_course_docs(
            db,
            operator_id=current_user.id,
            course_id=course_id,
            doc_ids=body.doc_ids,
        )
    )


@router.delete(
    "/{course_id}",
    summary="软删除课程",
    description="不删除已挂接文档。需要 course:delete。",
)
# 实现：软删除课程
def delete_course(
    course_id: UUID,
    current_user: Annotated[User, Depends(require_permission("course:delete"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    course_service.soft_delete_course(
        db, operator_id=current_user.id, course_id=course_id
    )
    return success()

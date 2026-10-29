"""F5：课程 HTTP 接口。

读：course:read，结果限制在可访问部门。
写与挂文档：course:manage；挂接文档须落在 get_visible_doc_ids。
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
    description="分页列出数据范围内的课程。需要 course:read。",
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
    description="部门不在范围内时 404。需要 course:read。",
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
    description="需要 course:manage；dept_id 须在数据范围内。",
)
# 实现：创建课程
def create_course(
    body: CourseCreate,
    current_user: Annotated[User, Depends(require_permission("course:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(
        course_service.create_course(
            db,
            operator_id=current_user.id,
            title=body.title,
            description=body.description,
            dept_id=body.dept_id,
        )
    )


@router.put(
    "/{course_id}",
    summary="更新课程",
    description="可改 title、description、dept_id。需要 course:manage。",
)
# 实现：更新课程元数据
def update_course(
    course_id: UUID,
    body: CourseUpdate,
    current_user: Annotated[User, Depends(require_permission("course:manage"))],
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
        )
    )


@router.put(
    "/{course_id}/docs",
    summary="替换课程文档",
    description="用 doc_ids 整体替换；文档须对操作者可见。需要 course:manage。",
)
# 实现：整体替换课程挂接文档
def replace_course_docs(
    course_id: UUID,
    body: CourseDocsUpdate,
    current_user: Annotated[User, Depends(require_permission("course:manage"))],
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
    description="不删除已挂接文档。需要 course:manage。",
)
# 实现：软删除课程
def delete_course(
    course_id: UUID,
    current_user: Annotated[User, Depends(require_permission("course:manage"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    course_service.soft_delete_course(
        db, operator_id=current_user.id, course_id=course_id
    )
    return success()

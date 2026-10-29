"""课程业务：部门范围内 CRUD、整体替换挂接文档。

挂接不放大文档权限：读文档仍走 get_visible_doc_ids；删课程不删文档。
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.system.course import Course, CourseDoc
from app.models.system.dept import Dept
from app.models.system.doc import Doc
from app.services.system import scope_service
from app.utils.pagination import page_offset


# 实现：查询课程已挂接的文档 id（稳定排序）
def _doc_ids_of(session: Session, course_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(CourseDoc.doc_id)
            .where(CourseDoc.course_id == course_id)
            .order_by(CourseDoc.doc_id)
        ).all()
    )


# 实现：课程转响应 dict（含 doc_ids）
def _to_dict(session: Session, course: Course) -> dict:
    return {
        "id": str(course.id),
        "title": course.title,
        "description": course.description,
        "dept_id": str(course.dept_id),
        "doc_ids": [str(did) for did in _doc_ids_of(session, course.id)],
        "created_at": course.created_at.isoformat() if course.created_at else None,
        "updated_at": course.updated_at.isoformat() if course.updated_at else None,
    }


# 实现：取操作者可访问部门集合
def _accessible_set(session: Session, operator_id: uuid.UUID) -> set[uuid.UUID]:
    return set(scope_service.get_accessible_dept_ids(session, operator_id))


# 实现：断言部门存在且在数据范围内
def _require_dept_in_scope(
    session: Session, operator_id: uuid.UUID, dept_id: uuid.UUID
) -> None:
    dept = session.scalar(
        select(Dept).where(Dept.id == dept_id, Dept.is_deleted.is_(False))
    )
    if dept is None or dept_id not in _accessible_set(session, operator_id):
        raise NotFoundError("部门不存在")


# 实现：按部门范围取未删课程，否则 404（不泄露越权存在）
def _require_course_in_scope(
    session: Session, operator_id: uuid.UUID, course_id: uuid.UUID
) -> Course:
    course = session.scalar(
        select(Course).where(Course.id == course_id, Course.is_deleted.is_(False))
    )
    if course is None or course.dept_id not in _accessible_set(session, operator_id):
        raise NotFoundError("课程不存在")
    return course


# 实现：整体替换 course_doc；文档须未删且落在 get_visible_doc_ids
def _replace_docs(
    session: Session, operator_id: uuid.UUID, course_id: uuid.UUID, doc_ids: list[uuid.UUID]
) -> None:
    unique_ids = list(dict.fromkeys(doc_ids))
    if unique_ids:
        visible = set(scope_service.get_visible_doc_ids(session, operator_id))
        # 先确认都是未删文档，再确认可见，统一用 404 避免泄露
        found = set(
            session.scalars(
                select(Doc.id).where(
                    Doc.id.in_(unique_ids),
                    Doc.is_deleted.is_(False),
                )
            ).all()
        )
        for did in unique_ids:
            if did not in found or did not in visible:
                raise NotFoundError("文档不存在")

    session.execute(delete(CourseDoc).where(CourseDoc.course_id == course_id))
    for did in unique_ids:
        session.add(CourseDoc(course_id=course_id, doc_id=did))


# 实现：分页列出数据范围内的未删课程
def list_courses(
    session: Session,
    *,
    operator_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    accessible = list(_accessible_set(session, operator_id))
    if not accessible:
        return [], 0

    total = (
        session.scalar(
            select(func.count())
            .select_from(Course)
            .where(Course.is_deleted.is_(False), Course.dept_id.in_(accessible))
        )
        or 0
    )
    rows = session.scalars(
        select(Course)
        .where(Course.is_deleted.is_(False), Course.dept_id.in_(accessible))
        .order_by(Course.created_at.desc(), Course.id)
        .offset(page_offset(page, page_size))
        .limit(page_size)
    ).all()
    return [_to_dict(session, c) for c in rows], int(total)


# 实现：课程详情
def get_course(
    session: Session, *, operator_id: uuid.UUID, course_id: uuid.UUID
) -> dict:
    return _to_dict(session, _require_course_in_scope(session, operator_id, course_id))


# 实现：创建课程（可顺带挂空文档列表）
def create_course(
    session: Session,
    *,
    operator_id: uuid.UUID,
    title: str,
    description: str | None,
    dept_id: uuid.UUID,
) -> dict:
    cleaned = title.strip()
    if not cleaned:
        raise ValidationFailedError("标题不能为空")
    _require_dept_in_scope(session, operator_id, dept_id)

    course = Course(
        title=cleaned,
        description=description,
        dept_id=dept_id,
        is_deleted=False,
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    return _to_dict(session, course)


# 实现：更新课程元数据（未传入的字段保持原值；description 可显式传 null 清空）
def update_course(
    session: Session,
    *,
    operator_id: uuid.UUID,
    course_id: uuid.UUID,
    title: str | None = None,
    description: str | None = None,
    dept_id: uuid.UUID | None = None,
    fields_set: set[str] | None = None,
) -> dict:
    course = _require_course_in_scope(session, operator_id, course_id)
    touched = fields_set or set()

    if "title" in touched and title is not None:
        cleaned = title.strip()
        if not cleaned:
            raise ValidationFailedError("标题不能为空")
        course.title = cleaned

    if "description" in touched:
        course.description = description

    if "dept_id" in touched and dept_id is not None:
        _require_dept_in_scope(session, operator_id, dept_id)
        course.dept_id = dept_id

    session.commit()
    session.refresh(course)
    return _to_dict(session, course)


# 实现：整体替换课程挂接文档
def replace_course_docs(
    session: Session,
    *,
    operator_id: uuid.UUID,
    course_id: uuid.UUID,
    doc_ids: list[uuid.UUID],
) -> dict:
    course = _require_course_in_scope(session, operator_id, course_id)
    _replace_docs(session, operator_id, course.id, doc_ids)
    session.commit()
    session.refresh(course)
    return _to_dict(session, course)


# 实现：软删除课程（不删文档、不强制清 course_doc）
def soft_delete_course(
    session: Session, *, operator_id: uuid.UUID, course_id: uuid.UUID
) -> None:
    course = _require_course_in_scope(session, operator_id, course_id)
    course.is_deleted = True
    session.commit()

"""文档业务：可见范围内列表/详情、上传落盘、元数据更新、软删除、下载路径。

读路径一律经 get_visible_doc_ids；不可见一律 404，不泄露是否存在。
阶段 1 不解析正文；软删除不删磁盘文件。
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.system.dept import Dept
from app.models.system.doc import Doc
from app.services.system import scope_service
from app.utils import files as file_utils
from app.utils.pagination import page_offset


# 实现：文档元数据转响应 dict（不含磁盘绝对路径）
def _to_dict(doc: Doc) -> dict:
    return {
        "id": str(doc.id),
        "title": doc.title,
        "dept_id": str(doc.dept_id),
        "original_filename": doc.original_filename,
        "extension": doc.extension,
        "size_bytes": doc.size_bytes,
        "sha256": doc.sha256,
        "uploaded_by": str(doc.uploaded_by),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


# 实现：取可见文档 id 集合
def _visible_set(session: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    return set(scope_service.get_visible_doc_ids(session, user_id))


# 实现：断言部门存在且在操作者可访问部门树内
def _require_dept_in_scope(
    session: Session, operator_id: uuid.UUID, dept_id: uuid.UUID
) -> None:
    dept = session.scalar(
        select(Dept).where(Dept.id == dept_id, Dept.is_deleted.is_(False))
    )
    accessible = set(scope_service.get_accessible_dept_ids(session, operator_id))
    if dept is None or dept_id not in accessible:
        raise NotFoundError("部门不存在")


# 实现：按可见性取文档；不可见或已删 → 404（读路径专用）
def _require_visible_doc(
    session: Session, operator_id: uuid.UUID, doc_id: uuid.UUID
) -> Doc:
    if doc_id not in _visible_set(session, operator_id):
        raise NotFoundError("文档不存在")
    doc = session.scalar(
        select(Doc).where(Doc.id == doc_id, Doc.is_deleted.is_(False))
    )
    if doc is None:
        raise NotFoundError("文档不存在")
    return doc


# 实现：写路径按部门范围取文档（不依赖 doc:read）；越权/已删 → 404
def _require_doc_in_dept_scope(
    session: Session, operator_id: uuid.UUID, doc_id: uuid.UUID
) -> Doc:
    doc = session.scalar(
        select(Doc).where(Doc.id == doc_id, Doc.is_deleted.is_(False))
    )
    accessible = set(scope_service.get_accessible_dept_ids(session, operator_id))
    if doc is None or doc.dept_id not in accessible:
        raise NotFoundError("文档不存在")
    return doc


# 实现：分页列出当前用户可见文档
def list_docs(
    session: Session,
    *,
    operator_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    visible = list(_visible_set(session, operator_id))
    if not visible:
        return [], 0

    total = (
        session.scalar(
            select(func.count()).select_from(Doc).where(Doc.id.in_(visible))
        )
        or 0
    )
    rows = session.scalars(
        select(Doc)
        .where(Doc.id.in_(visible))
        .order_by(Doc.created_at.desc(), Doc.id)
        .offset(page_offset(page, page_size))
        .limit(page_size)
    ).all()
    return [_to_dict(d) for d in rows], int(total)


# 实现：文档详情（不可见 → 404）
def get_doc(
    session: Session, *, operator_id: uuid.UUID, doc_id: uuid.UUID
) -> dict:
    return _to_dict(_require_visible_doc(session, operator_id, doc_id))


# 实现：multipart 上传：校验文件 → 落盘 → 写元数据行
def create_doc(
    session: Session,
    *,
    operator_id: uuid.UUID,
    title: str,
    dept_id: uuid.UUID,
    filename: str | None,
    content: bytes,
) -> dict:
    title = title.strip()
    if not title:
        raise ValidationFailedError("标题不能为空")

    _require_dept_in_scope(session, operator_id, dept_id)
    ext = file_utils.extension_of(filename)
    original = (filename or f"upload.{ext}").strip()[:255]
    storage_key, size_bytes, sha256 = file_utils.save_upload_bytes(
        content=content, ext=ext
    )

    doc = Doc(
        title=title,
        dept_id=dept_id,
        original_filename=original,
        extension=ext,
        size_bytes=size_bytes,
        storage_key=storage_key,
        sha256=sha256,
        uploaded_by=operator_id,
        is_deleted=False,
    )
    session.add(doc)
    try:
        session.commit()
    except Exception:
        # DB 失败时尽量清掉刚写入的文件，避免孤儿文件堆积
        path = file_utils.resolve_stored_path(storage_key)
        path.unlink(missing_ok=True)
        raise
    session.refresh(doc)
    return _to_dict(doc)


# 实现：更新标题/归属部门（不换文件）；目标与新部门均须在可访问部门内
def update_doc(
    session: Session,
    *,
    operator_id: uuid.UUID,
    doc_id: uuid.UUID,
    title: str | None,
    dept_id: uuid.UUID | None,
) -> dict:
    doc = _require_doc_in_dept_scope(session, operator_id, doc_id)

    if title is not None:
        cleaned = title.strip()
        if not cleaned:
            raise ValidationFailedError("标题不能为空")
        doc.title = cleaned

    if dept_id is not None:
        _require_dept_in_scope(session, operator_id, dept_id)
        doc.dept_id = dept_id

    session.commit()
    session.refresh(doc)
    return _to_dict(doc)


# 实现：软删除文档（不删磁盘文件）；按部门范围，不依赖 doc:read
def soft_delete_doc(
    session: Session, *, operator_id: uuid.UUID, doc_id: uuid.UUID
) -> None:
    doc = _require_doc_in_dept_scope(session, operator_id, doc_id)
    doc.is_deleted = True
    session.commit()


# 实现：解析可下载的绝对路径与原始文件名；不可见 → 404
def get_download_info(
    session: Session, *, operator_id: uuid.UUID, doc_id: uuid.UUID
) -> tuple[Path, str, str]:
    doc = _require_visible_doc(session, operator_id, doc_id)
    path = file_utils.resolve_stored_path(doc.storage_key)
    if not path.is_file():
        raise NotFoundError("文件不存在")
    media = "application/pdf" if doc.extension == "pdf" else "text/markdown; charset=utf-8"
    return path, doc.original_filename, media

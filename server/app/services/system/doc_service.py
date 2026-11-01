"""文档业务：可见范围内列表/详情、上传落盘、元数据与 audience、软删除、下载路径。

读路径一律经 get_visible_doc_ids；不可见一律 404，不泄露是否存在。
写路径：归属部门受管理范围约束；audience 走 resolve_audience_dept_ids（B1/B3）。
阶段 1 不解析正文；软删除不删磁盘文件。
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.system.dept import Dept
from app.models.system.doc import Doc, DocAudienceDept
from app.services.system import scope_service
from app.storage import get_storage
from app.utils import files as file_utils
from app.utils.office_preview import OFFICE_EXTENSIONS, convert_office_to_pdf
from app.utils.pagination import page_offset

logger = logging.getLogger(__name__)


# 实现：读取文档 audience 部门 id 列表
def _audience_dept_ids(session: Session, doc_id: uuid.UUID) -> list[str]:
    rows = session.scalars(
        select(DocAudienceDept.dept_id)
        .where(DocAudienceDept.doc_id == doc_id)
        .order_by(DocAudienceDept.dept_id)
    ).all()
    return [str(d) for d in rows]


# 实现：是否已有可用预览件（pdf/md 视作可直接预览）
def _preview_ready(doc: Doc) -> bool:
    if doc.extension in {"pdf", "md"}:
        return True
    if doc.extension not in OFFICE_EXTENSIONS:
        return False
    key = doc.preview_storage_key
    return bool(key and get_storage().exists(key))


# 实现：文档元数据转响应 dict（含 audience；不含磁盘绝对路径/存储键）
def _to_dict(session: Session, doc: Doc) -> dict:
    return {
        "id": str(doc.id),
        "title": doc.title,
        "dept_id": str(doc.dept_id),
        "audience_dept_ids": _audience_dept_ids(session, doc.id),
        "original_filename": doc.original_filename,
        "extension": doc.extension,
        "size_bytes": doc.size_bytes,
        "sha256": doc.sha256,
        "uploaded_by": str(doc.uploaded_by),
        "preview_ready": _preview_ready(doc),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


# 实现：下载 Content-Type
def _media_for_extension(ext: str) -> str:
    return {
        "pdf": "application/pdf",
        "md": "text/markdown; charset=utf-8",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(ext, "application/octet-stream")


# 实现：为 office 文档生成并保存预览 PDF；已有则跳过
def ensure_office_preview(session: Session, doc: Doc) -> None:
    if doc.extension not in OFFICE_EXTENSIONS:
        return
    if doc.preview_storage_key and get_storage().exists(doc.preview_storage_key):
        return

    original = get_storage().read(doc.storage_key)
    pdf_bytes = convert_office_to_pdf(content=original, ext=doc.extension)
    preview_key = f"previews/{file_utils.build_storage_key('pdf')}"
    get_storage().put(preview_key, pdf_bytes)
    doc.preview_storage_key = preview_key
    session.commit()
    session.refresh(doc)


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


# 实现：整体替换文档 audience 行
def _replace_audience(
    session: Session, doc_id: uuid.UUID, audience_dept_ids: list[uuid.UUID]
) -> None:
    session.execute(delete(DocAudienceDept).where(DocAudienceDept.doc_id == doc_id))
    for dept_id in audience_dept_ids:
        session.add(DocAudienceDept(doc_id=doc_id, dept_id=dept_id))


# 实现：转义 ILIKE 通配符，避免用户输入 %/_ 扩大匹配
def _ilike_pattern(raw: str) -> str:
    escaped = (
        raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"


# 实现：分页列出当前用户可见文档（可选 title 模糊筛选）
def list_docs(
    session: Session,
    *,
    operator_id: uuid.UUID,
    page: int,
    page_size: int,
    title: str | None = None,
) -> tuple[list[dict], int]:
    visible = list(_visible_set(session, operator_id))
    if not visible:
        return [], 0

    conditions = [Doc.id.in_(visible), Doc.is_deleted.is_(False)]
    if title is not None:
        cleaned = title.strip()
        if cleaned:
            conditions.append(Doc.title.ilike(_ilike_pattern(cleaned), escape="\\"))

    total = (
        session.scalar(select(func.count()).select_from(Doc).where(*conditions))
        or 0
    )
    rows = session.scalars(
        select(Doc)
        .where(*conditions)
        .order_by(Doc.created_at.desc(), Doc.id)
        .offset(page_offset(page, page_size))
        .limit(page_size)
    ).all()
    return [_to_dict(session, d) for d in rows], int(total)


# 实现：文档详情（不可见 → 404）
def get_doc(
    session: Session, *, operator_id: uuid.UUID, doc_id: uuid.UUID
) -> dict:
    return _to_dict(session, _require_visible_doc(session, operator_id, doc_id))


# 实现：multipart 上传：校验文件 → 落盘 → 写元数据 + audience
def create_doc(
    session: Session,
    *,
    operator_id: uuid.UUID,
    title: str,
    dept_id: uuid.UUID,
    filename: str | None,
    content: bytes,
    audience_dept_ids: list[uuid.UUID] | None = None,
) -> dict:
    title = title.strip()
    if not title:
        raise ValidationFailedError("标题不能为空")

    _require_dept_in_scope(session, operator_id, dept_id)
    audience = scope_service.resolve_audience_dept_ids(
        session,
        operator_id=operator_id,
        owner_dept_id=dept_id,
        audience_dept_ids=audience_dept_ids,
    )
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
    session.flush()
    _replace_audience(session, doc.id, audience)
    try:
        session.commit()
    except Exception:
        # DB 失败时尽量清掉刚写入的对象，避免孤儿文件堆积
        file_utils.delete_stored(storage_key)
        raise
    session.refresh(doc)

    # 办公文档：上传成功后再尽力生成预览；失败不影响入库
    if ext in OFFICE_EXTENSIONS:
        try:
            ensure_office_preview(session, doc)
        except Exception as exc:  # noqa: BLE001 — 预览失败不阻断上传
            logger.warning("office preview after upload failed doc=%s: %s", doc.id, exc)
            session.refresh(doc)

    return _to_dict(session, doc)


# 实现：更新标题/归属/audience；目标与新部门均须在可访问部门内
def update_doc(
    session: Session,
    *,
    operator_id: uuid.UUID,
    doc_id: uuid.UUID,
    title: str | None,
    dept_id: uuid.UUID | None,
    audience_dept_ids: list[uuid.UUID] | None = None,
    audience_provided: bool = False,
) -> dict:
    doc = _require_doc_in_dept_scope(session, operator_id, doc_id)

    if title is not None:
        cleaned = title.strip()
        if not cleaned:
            raise ValidationFailedError("标题不能为空")
        doc.title = cleaned

    owner_changed = False
    if dept_id is not None:
        _require_dept_in_scope(session, operator_id, dept_id)
        if dept_id != doc.dept_id:
            owner_changed = True
        doc.dept_id = dept_id

    # 显式传 audience、改归属、或部门官（B3 每次写死本部门）时重写 audience
    force_own_dept = not scope_service.can_customize_audience(session, operator_id)
    if audience_provided or owner_changed or force_own_dept:
        incoming = audience_dept_ids if audience_provided else None
        audience = scope_service.resolve_audience_dept_ids(
            session,
            operator_id=operator_id,
            owner_dept_id=doc.dept_id,
            audience_dept_ids=incoming,
        )
        _replace_audience(session, doc.id, audience)

    session.commit()
    session.refresh(doc)
    return _to_dict(session, doc)


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
    if not get_storage().exists(doc.storage_key):
        raise NotFoundError("文件不存在")
    path = file_utils.resolve_stored_path(doc.storage_key)
    return path, doc.original_filename, _media_for_extension(doc.extension)


# 实现：预览流路径（可见性同下载）；office 按需转 PDF
def get_preview_info(
    session: Session, *, operator_id: uuid.UUID, doc_id: uuid.UUID
) -> tuple[Path, str, str]:
    doc = _require_visible_doc(session, operator_id, doc_id)

    if doc.extension in {"pdf", "md"}:
        if not get_storage().exists(doc.storage_key):
            raise NotFoundError("文件不存在")
        path = file_utils.resolve_stored_path(doc.storage_key)
        name = doc.original_filename
        return path, name, _media_for_extension(doc.extension)

    if doc.extension in OFFICE_EXTENSIONS:
        ensure_office_preview(session, doc)
        session.refresh(doc)
        key = doc.preview_storage_key
        if not key or not get_storage().exists(key):
            raise ValidationFailedError("预览文件不可用，请下载原件")
        path = file_utils.resolve_stored_path(key)
        stem = Path(doc.original_filename).stem or doc.title
        return path, f"{stem}.pdf", "application/pdf"

    raise ValidationFailedError(f"不支持预览的文件类型: .{doc.extension}")

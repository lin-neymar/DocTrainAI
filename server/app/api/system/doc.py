"""F4：文档 HTTP 接口。

读（列表/详情/下载）：doc:read + get_visible_doc_ids。
上传/改元数据：doc:upload；软删除：doc:delete。
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.response import success
from app.database import get_db
from app.models.system.user import User
from app.schemas.common import page_data
from app.schemas.system.doc import DocUpdate
from app.services.system import doc_service

router = APIRouter(prefix="/docs", tags=["docs"])


@router.get(
    "",
    summary="文档列表",
    description="分页列出当前用户可见文档。需要 doc:read。",
)
# 实现：分页列出可见文档
def list_docs(
    current_user: Annotated[User, Depends(require_permission("doc:read"))],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    items, total = doc_service.list_docs(
        db, operator_id=current_user.id, page=page, page_size=page_size
    )
    return success(page_data(items=items, total=total, page=page, page_size=page_size))


@router.get(
    "/{doc_id}",
    summary="文档详情",
    description="不可见时返回 404。需要 doc:read。",
)
# 实现：文档元数据详情
def get_doc(
    doc_id: UUID,
    current_user: Annotated[User, Depends(require_permission("doc:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(
        doc_service.get_doc(db, operator_id=current_user.id, doc_id=doc_id)
    )


@router.get(
    "/{doc_id}/file",
    summary="下载原文件",
    description="返回磁盘上的原文件；不可见时 404。需要 doc:read。",
)
# 实现：按可见性下载原文件
def download_doc_file(
    doc_id: UUID,
    current_user: Annotated[User, Depends(require_permission("doc:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    path, filename, media_type = doc_service.get_download_info(
        db, operator_id=current_user.id, doc_id=doc_id
    )
    return FileResponse(path=path, filename=filename, media_type=media_type)


@router.post(
    "",
    summary="上传文档",
    description="multipart：title、dept_id、file。需要 doc:upload；部门须在数据范围内。",
)
# 实现：上传并创建文档元数据
async def create_doc(
    current_user: Annotated[User, Depends(require_permission("doc:upload"))],
    db: Annotated[Session, Depends(get_db)],
    title: Annotated[str, Form(min_length=1, max_length=256)],
    dept_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> dict:
    content = await file.read()
    data = doc_service.create_doc(
        db,
        operator_id=current_user.id,
        title=title,
        dept_id=dept_id,
        filename=file.filename,
        content=content,
    )
    return success(data)


@router.put(
    "/{doc_id}",
    summary="更新文档元数据",
    description="可改 title、dept_id；不换原文件。需要 doc:upload。",
)
# 实现：更新文档标题/部门
def update_doc(
    doc_id: UUID,
    body: DocUpdate,
    current_user: Annotated[User, Depends(require_permission("doc:upload"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return success(
        doc_service.update_doc(
            db,
            operator_id=current_user.id,
            doc_id=doc_id,
            title=body.title,
            dept_id=body.dept_id,
        )
    )


@router.delete(
    "/{doc_id}",
    summary="软删除文档",
    description="不删除磁盘文件。需要 doc:delete；不可见时 404。",
)
# 实现：软删除文档
def delete_doc(
    doc_id: UUID,
    current_user: Annotated[User, Depends(require_permission("doc:delete"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    doc_service.soft_delete_doc(
        db, operator_id=current_user.id, doc_id=doc_id
    )
    return success()

"""混合检索 HTTP 接口：可见性前置，权限复用 doc:read。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.response import success
from app.database import get_db
from app.models.system.user import User
from app.schemas.ai_ext.retrieval import RetrievalOut, RetrievalRequest
from app.services.ai_ext import retrieval_service

router = APIRouter(prefix="/retrieval", tags=["retrieval"])

@router.post(
    "",
    summary="混合检索",
    description=(
        "在可见文档内做向量 + 全文两路检索，归一化加权后返回 TopK 分片。"
        "需要 doc:read。"
    ),
)
def search(
    body: RetrievalRequest,
    current_user: Annotated[User, Depends(require_permission("doc:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    items = retrieval_service.search_chunks(
        db,
        user_id=current_user.id,
        query=body.query,
        top_k=body.top_k,
    )
    return success(RetrievalOut(items=items).model_dump(mode="json"))
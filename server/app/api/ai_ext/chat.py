"""对话 HTTP：会话 CRUD 与 SSE 问答。权限统一 agent:chat。"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.response import success
from app.database import get_db
from app.models.system.user import User
from app.schemas.ai_ext.chat import (
    ChatMessageOut,
    ChatSessionOut,
    MessageBatchDelete,
    MessageCreate,
)
from app.schemas.common import page_data
from app.services.ai_ext import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", summary="新建会话", description="需要 agent:chat。")
def create_session(
    current_user: Annotated[User, Depends(require_permission("agent:chat"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    chat_session = chat_service.create_session(db, user_id=current_user.id)
    db.commit()
    return success(ChatSessionOut.model_validate(chat_session).model_dump(mode="json"))


@router.get(
    "/sessions",
    summary="会话列表",
    description="按更新时间倒序分页（默认 20，最大 100）。需要 agent:chat。",
)
def list_sessions(
    current_user: Annotated[User, Depends(require_permission("agent:chat"))],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    items, total = chat_service.list_sessions(
        db, user_id=current_user.id, page=page, page_size=page_size
    )
    return success(
        page_data(
            items=[
                ChatSessionOut.model_validate(i).model_dump(mode="json") for i in items
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/sessions/{session_id}/messages",
    summary="会话消息",
    description="按时间正序，含引用。他人会话 404。需要 agent:chat。",
)
def list_messages(
    session_id: UUID,
    current_user: Annotated[User, Depends(require_permission("agent:chat"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    # 先做归属校验（他人会话 404），再取消息
    chat_service.get_owned_session(db, current_user.id, session_id)
    messages = chat_service.list_messages(db, session_id)
    return success(
        [ChatMessageOut.model_validate(m).model_dump(mode="json") for m in messages]
    )


@router.post(
    "/sessions/{session_id}/messages",
    summary="发送消息（SSE 流式）",
    description=(
        "事件只有 citation / delta / done / error 四种，done 为最后事件。"
        "401/403/404/422 在流建立前以 JSON 返回。需要 agent:chat。"
    ),
)
def send_message(
    session_id: UUID,
    body: MessageCreate,
    current_user: Annotated[User, Depends(require_permission("agent:chat"))],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    chat_session = chat_service.get_owned_session(db, current_user.id, session_id)
    history = chat_service.recent_history(db, chat_session.id)
    return StreamingResponse(
        chat_service.stream_chat(
            db,
            user_id=current_user.id,
            session_id=chat_session.id,
            content=body.content,
            history=history,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete(
    "/sessions/{session_id}/messages",
    summary="批量删除消息",
    description=(
        "硬删除指定消息；删 user 必连带下一条 assistant，删 assistant 必连带前一条 user。"
        "他人会话或消息不属于该会话 404。需要 agent:chat。"
    ),
)
def delete_messages(
    session_id: UUID,
    body: MessageBatchDelete,
    current_user: Annotated[User, Depends(require_permission("agent:chat"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    deleted = chat_service.delete_messages(
        db,
        user_id=current_user.id,
        session_id=session_id,
        message_ids=body.message_ids,
    )
    db.commit()
    return success({"deleted_count": deleted})


@router.delete(
    "/sessions/{session_id}",
    summary="软删除会话",
    description="消息与调用日志保留（审计）。他人/不存在/已删会话 404。需要 agent:chat。",
)
def delete_session(
    session_id: UUID,
    current_user: Annotated[User, Depends(require_permission("agent:chat"))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    chat_service.soft_delete_session(db, user_id=current_user.id, session_id=session_id)
    db.commit()
    return success()
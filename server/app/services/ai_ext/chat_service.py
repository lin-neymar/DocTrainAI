"""对话服务：会话 CRUD、SSE 事件流与消息/调用日志落库。

对应 SERVER_SPEC 阶段 3 接口：
- 会话只属于创建者；他人会话一律 404（与不存在同态，不泄露资源存在性）；
- 发送消息走 SSE 流，事件只有 citation / delta / done / error 四种，done 为最后事件；
- 流正常结束后用户消息、助手消息与调用日志一起落库；error 时不落库。
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import NotFoundError
from app.models.ai_ext.chat import (
    CHAT_ROLE_ASSISTANT,
    CHAT_ROLE_USER,
    ChatCallLog,
    ChatMessage,
    ChatSession,
)
from app.services.ai_ext.agent_graph import run_agent
from app.utils.pagination import page_offset


def create_session(db: Session, *, user_id: uuid.UUID) -> ChatSession:
    chat_session = ChatSession(user_id=user_id, is_deleted=False)
    db.add(chat_session)
    db.flush()
    return chat_session


def list_sessions(
    db: Session, *, user_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[ChatSession], int]:
    total = db.scalar(
        select(func.count())
        .select_from(ChatSession)
        .where(ChatSession.user_id == user_id, ChatSession.is_deleted.is_(False))
    ) or 0
    rows = db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user_id, ChatSession.is_deleted.is_(False))
        .order_by(ChatSession.updated_at.desc())
        .offset(page_offset(page, page_size))
        .limit(page_size)
    ).all()
    return list(rows), total


# 实现：归属校验——他人会话与不存在同样 404
def get_owned_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> ChatSession:
    chat_session = db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
        )
    )
    if chat_session is None:
        raise NotFoundError()
    return chat_session


# 实现：软删除会话——消息与调用日志保留（审计），删除后一切访问路径 404
def soft_delete_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    chat_session = get_owned_session(db, user_id, session_id)
    chat_session.is_deleted = True


def list_messages(db: Session, session_id: uuid.UUID) -> list[ChatMessage]:
    return list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        ).all()
    )


def _pair_maps(
    messages: list[ChatMessage],
) -> tuple[dict[uuid.UUID, uuid.UUID], dict[uuid.UUID, uuid.UUID]]:
    """相邻 user→assistant 配对（与前端一轮对话定义一致）。"""
    user_to_assistant: dict[uuid.UUID, uuid.UUID] = {}
    assistant_to_user: dict[uuid.UUID, uuid.UUID] = {}
    for i, message in enumerate(messages):
        if message.role != CHAT_ROLE_USER:
            continue
        if i + 1 >= len(messages):
            continue
        nxt = messages[i + 1]
        if nxt.role == CHAT_ROLE_ASSISTANT:
            user_to_assistant[message.id] = nxt.id
            assistant_to_user[nxt.id] = message.id
    return user_to_assistant, assistant_to_user


def expand_message_ids_for_delete(
    message_ids: list[uuid.UUID], messages: list[ChatMessage]
) -> set[uuid.UUID]:
    """删问题必删回答、删回答必删问题：闭包扩展选中集。"""
    user_to_assistant, assistant_to_user = _pair_maps(messages)
    expanded: set[uuid.UUID] = set()
    for mid in message_ids:
        expanded.add(mid)
        partner = user_to_assistant.get(mid) or assistant_to_user.get(mid)
        if partner is not None:
            expanded.add(partner)
    return expanded


def delete_messages(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    message_ids: list[uuid.UUID],
) -> int:
    get_owned_session(db, user_id, session_id)
    all_messages = list_messages(db, session_id)
    known_ids = {m.id for m in all_messages}
    for mid in message_ids:
        if mid not in known_ids:
            raise NotFoundError()
    expanded = expand_message_ids_for_delete(message_ids, all_messages)
    if not expanded:
        return 0
    db.execute(
        delete(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.id.in_(expanded),
        )
    )
    chat_session = get_owned_session(db, user_id, session_id)
    chat_session.updated_at = datetime.now(timezone.utc)
    db.flush()
    return len(expanded)


# 实现：取最近 N 条历史（MEMORY_TURNS_MESSAGES），按时间正序返回
def recent_history(db: Session, session_id: uuid.UUID) -> list[dict[str, str]]:
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(settings.memory_turns_messages)
    ).all()
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]


def _save_message(
    db: Session,
    *,
    session_id: uuid.UUID,
    role: str,
    content: str,
    refused: bool,
    citations: list[dict] | None,
) -> ChatMessage:
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        refused=refused,
        citations=citations or None,
    )
    db.add(message)
    db.flush()
    return message


def _log_call(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    duration_ms: int,
    chunk_ids: list[str],
    refused: bool,
) -> None:
    db.add(
        ChatCallLog(
            user_id=user_id,
            session_id=session_id,
            model=settings.chat_model,
            duration_ms=duration_ms,
            chunk_ids=chunk_ids or None,
            refused=refused,
        )
    )


# 实现：SSE 事件帧——event 行 + 单行 JSON data + 空行
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# 实现：对话事件流——worker 线程跑 Agent（同步阻塞），回调入队，主循环出队转发
def stream_chat(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    content: str,
    history: list[dict[str, str]],
) -> Iterator[str]:
    events: queue.Queue[tuple[str, dict] | None] = queue.Queue()
    outcome: dict = {}
    started = time.monotonic()

    def worker() -> None:
        try:
            result = run_agent(
                db,
                user_id=user_id,
                question=content,
                history=history,
                on_token=lambda text: events.put(("delta", {"text": text})),
                on_citation=lambda item: events.put(("citation", item)),
            )
            outcome["result"] = result
        except Exception as exc:
            # 模型未配置、调用失败等中断性错误 → error 事件后关流
            outcome["error"] = str(exc)
        finally:
            events.put(None)

    thread = threading.Thread(target=worker)
    thread.start()
    for item in iter(events.get, None):
        event, data = item
        yield _sse(event, data)
    thread.join()

    if "error" in outcome:
        yield _sse("error", {"message": outcome["error"]})
        return

    result = outcome["result"]
    user_message = _save_message(
        db,
        session_id=session_id,
        role=CHAT_ROLE_USER,
        content=content,
        refused=False,
        citations=None,
    )
    message = _save_message(
        db,
        session_id=session_id,
        role=CHAT_ROLE_ASSISTANT,
        content=result["answer"],
        refused=result["refused"],
        citations=result.get("citations") or [],
    )
    _log_call(
        db,
        user_id=user_id,
        session_id=session_id,
        duration_ms=int((time.monotonic() - started) * 1000),
        chunk_ids=result.get("chunk_ids") or [],
        refused=result["refused"],
    )
    db.commit()
    # done 必须是最后一个事件：先落库拿到 message_id 再发送
    yield _sse(
        "done",
        {
            "message_id": str(message.id),
            "user_message_id": str(user_message.id),
            "refused": result["refused"],
        },
    )
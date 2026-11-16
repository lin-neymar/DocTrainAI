"""阶段 3：对话接口测试（需 Postgres 已迁移；库未就绪则 skip）。

对应 SERVER_SPEC 阶段 3：
- 全部接口需要 agent:chat，无权限 403；
- 会话只属于创建者，他人会话一律 404；
- SSE 事件只有 citation / delta / done / error 四种，done 最后；
- 流正常结束后用户消息、助手消息与调用日志落库。
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.ai_ext.chat import (
    CHAT_ROLE_ASSISTANT,
    CHAT_ROLE_USER,
    ChatCallLog,
    ChatMessage,
    ChatSession,
)
from app.models.system.dept import Dept
from app.models.system.role import Role
from app.models.system.user import User, UserRole
from app.services.ai_ext import chat_service
from scripts.seed import run_seed

client = TestClient(app)


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _ensure_seeded() -> None:
    with SessionLocal() as session:
        run_seed(session)
        session.commit()


def _login(username: str, password: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    try:
        _ensure_seeded()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")
    return _login(settings.init_admin_username, settings.init_admin_password)


# 实现：造一个无角色的普通用户（登录没问题，但没有任何权限码）
def _create_bare_user() -> tuple[str, str]:
    password = "bare-pass-1"
    with SessionLocal() as session:
        root = session.scalar(
            select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
        )
        user = User(
            username=f"bare_{uuid.uuid4().hex[:8]}",
            password_hash=_hash_password(password),
            dept_id=root.id,
            is_deleted=False,
        )
        session.add(user)
        session.commit()
        return user.username, password


# 实现：造一个带 staff 角色（有 agent:chat）的普通用户，用于「他人会话 404」场景
def _create_staff_user() -> tuple[str, str]:
    password = "staff-pass-1"
    with SessionLocal() as session:
        root = session.scalar(
            select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
        )
        staff_role = session.scalar(
            select(Role).where(Role.code == "staff", Role.is_deleted.is_(False))
        )
        user = User(
            username=f"agent_{uuid.uuid4().hex[:8]}",
            password_hash=_hash_password(password),
            dept_id=root.id,
            is_deleted=False,
        )
        session.add(user)
        session.flush()
        session.add(UserRole(user_id=user.id, role_id=staff_role.id))
        session.commit()
        return user.username, password


def test_chat_requires_agent_chat_permission() -> None:
    """无 agent:chat → 403。"""
    try:
        _ensure_seeded()
        username, password = _create_bare_user()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")
    headers = _login(username, password)
    resp = client.post("/api/v1/chat/sessions", headers=headers)
    assert resp.status_code == 403


def test_create_session_and_list(admin_headers) -> None:
    """新建会话 → 列表能查到，且带分页字段。"""
    resp = client.post("/api/v1/chat/sessions", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"]
    assert data["created_at"]

    resp = client.get("/api/v1/chat/sessions", headers=admin_headers)
    assert resp.status_code == 200
    page = resp.json()["data"]
    assert page["total"] >= 1
    ids = {item["id"] for item in page["items"]}
    assert data["id"] in ids


def test_other_user_session_returns_404(admin_headers) -> None:
    """他人会话与不存在同态 404：读消息、发消息都拒绝。"""
    resp = client.post("/api/v1/chat/sessions", headers=admin_headers)
    session_id = resp.json()["data"]["id"]

    username, password = _create_staff_user()
    other = _login(username, password)

    resp = client.get(
        f"/api/v1/chat/sessions/{session_id}/messages", headers=other
    )
    assert resp.status_code == 404

    resp = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "你好"},
        headers=other,
    )
    assert resp.status_code == 404


def test_send_message_streams_sse_and_persists(admin_headers, monkeypatch) -> None:
    """SSE 事件序列正确（citation 先于 delta、done 最后），且消息与调用日志落库。"""
    resp = client.post("/api/v1/chat/sessions", headers=admin_headers)
    session_id = resp.json()["data"]["id"]

    # 假 Agent：先回调引用，再发三段 delta，返回脚本化结果
    def fake_run_agent(
        session, *, user_id, question, history, on_token=None, on_citation=None
    ):
        citation = {
            "doc_id": "22222222-2222-2222-2222-222222222222",
            "doc_title": "员工手册",
            "chunk_id": "11111111-1111-1111-1111-111111111111",
            "location": {"ext": "md"},
            "snippet": "员工每年享有五天带薪年假。",
        }
        if on_citation:
            on_citation(citation)
        for token in ["员工每年", "享有五天", "带薪年假"]:
            if on_token:
                on_token(token)
        return {
            "answer": "员工每年享有五天带薪年假",
            "refused": False,
            "citations": [citation],
            "chunk_ids": ["11111111-1111-1111-1111-111111111111"],
        }

    monkeypatch.setattr(chat_service, "run_agent", fake_run_agent)

    resp = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "年假有几天？"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    body = resp.text
    assert "event: citation" in body
    assert "event: delta" in body
    assert "event: done" in body
    assert "event: error" not in body
    idx_citation = body.index("event: citation")
    idx_delta = body.index("event: delta")
    idx_done = body.index("event: done")
    assert idx_citation < idx_delta < idx_done
    assert '"员工手册"' in body
    assert '"user_message_id"' in body

    # 落库断言：用户消息 + 助手消息（含引用）+ 一条调用日志
    with SessionLocal() as session:
        messages = session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        ).all()
        assert len(messages) == 2
        assert messages[0].role == CHAT_ROLE_USER
        assert messages[0].content == "年假有几天？"
        assert messages[1].role == CHAT_ROLE_ASSISTANT
        assert messages[1].refused is False
        assert messages[1].citations[0]["doc_title"] == "员工手册"

        log = session.scalar(
            select(ChatCallLog).where(ChatCallLog.session_id == session_id)
        )
        assert log is not None
        assert log.refused is False
        assert log.chunk_ids == ["11111111-1111-1111-1111-111111111111"]
        assert log.model == settings.chat_model


def test_send_message_error_event_on_failure(admin_headers, monkeypatch) -> None:
    """Agent 抛错 → 只发 error 事件关流，不落任何消息。"""
    resp = client.post("/api/v1/chat/sessions", headers=admin_headers)
    session_id = resp.json()["data"]["id"]

    def broken_run_agent(
        session, *, user_id, question, history, on_token=None, on_citation=None
    ):
        raise RuntimeError("模型不可用")

    monkeypatch.setattr(chat_service, "run_agent", broken_run_agent)

    resp = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "年假有几天？"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.text
    assert "event: error" in body
    assert "event: done" not in body

    with SessionLocal() as session:
        count = len(
            session.scalars(
                select(ChatMessage).where(ChatMessage.session_id == session_id)
            ).all()
        )
    assert count == 0


def test_delete_own_session_keeps_messages(admin_headers, monkeypatch) -> None:
    """软删除自己的会话：访问路径全 404，消息与调用日志保留（审计）。"""
    resp = client.post("/api/v1/chat/sessions", headers=admin_headers)
    session_id = resp.json()["data"]["id"]

    def fake_run_agent(
        session, *, user_id, question, history, on_token=None, on_citation=None
    ):
        return {"answer": "好的", "refused": False, "citations": [], "chunk_ids": []}

    monkeypatch.setattr(chat_service, "run_agent", fake_run_agent)
    resp = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "你好"},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    resp = client.delete(f"/api/v1/chat/sessions/{session_id}", headers=admin_headers)
    assert resp.status_code == 200

    # 列表不含该会话；读消息 404
    resp = client.get("/api/v1/chat/sessions", headers=admin_headers)
    ids = {item["id"] for item in resp.json()["data"]["items"]}
    assert session_id not in ids
    resp = client.get(
        f"/api/v1/chat/sessions/{session_id}/messages", headers=admin_headers
    )
    assert resp.status_code == 404

    # 数据库：会话软删除，消息与调用日志仍保留
    with SessionLocal() as session:
        chat_session = session.get(ChatSession, uuid.UUID(session_id))
        assert chat_session.is_deleted is True
        messages = session.scalars(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
        ).all()
        assert len(messages) == 2
        log = session.scalar(
            select(ChatCallLog).where(ChatCallLog.session_id == session_id)
        )
        assert log is not None


def test_delete_other_user_session_returns_404(admin_headers) -> None:
    """他人会话删除与不存在同态 404（不泄露资源存在性）。"""
    resp = client.post("/api/v1/chat/sessions", headers=admin_headers)
    session_id = resp.json()["data"]["id"]

    username, password = _create_staff_user()
    other = _login(username, password)

    resp = client.delete(f"/api/v1/chat/sessions/{session_id}", headers=other)
    assert resp.status_code == 404


def _send_one_turn(admin_headers, session_id: str, monkeypatch, question: str = "你好") -> None:
    def fake_run_agent(
        session, *, user_id, question, history, on_token=None, on_citation=None
    ):
        if on_token:
            on_token("好的")
        return {"answer": "好的", "refused": False, "citations": [], "chunk_ids": []}

    monkeypatch.setattr(chat_service, "run_agent", fake_run_agent)
    resp = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": question},
        headers=admin_headers,
    )
    assert resp.status_code == 200


def test_delete_messages_expands_user_assistant_pair(admin_headers, monkeypatch) -> None:
    """只传 user message_id 时连带删除配对 assistant。"""
    resp = client.post("/api/v1/chat/sessions", headers=admin_headers)
    session_id = resp.json()["data"]["id"]
    _send_one_turn(admin_headers, session_id, monkeypatch, "第一轮")
    _send_one_turn(admin_headers, session_id, monkeypatch, "第二轮")

    with SessionLocal() as session:
        messages = session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        ).all()
        assert len(messages) == 4
        first_user_id = str(messages[0].id)

    resp = client.request(
        "DELETE",
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"message_ids": [first_user_id]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted_count"] == 2

    with SessionLocal() as session:
        remaining = session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        ).all()
        assert len(remaining) == 2
        assert remaining[0].content == "第二轮"
        assert remaining[1].content == "好的"

    resp = client.get(
        f"/api/v1/chat/sessions/{session_id}/messages", headers=admin_headers
    )
    assert len(resp.json()["data"]) == 2


def test_delete_messages_foreign_id_returns_404(admin_headers, monkeypatch) -> None:
    """消息不属于该会话（或不存在）时 404。"""
    resp = client.post("/api/v1/chat/sessions", headers=admin_headers)
    session_id = resp.json()["data"]["id"]
    resp2 = client.post("/api/v1/chat/sessions", headers=admin_headers)
    other_session_id = resp2.json()["data"]["id"]
    _send_one_turn(admin_headers, other_session_id, monkeypatch)

    with SessionLocal() as session:
        foreign = session.scalars(
            select(ChatMessage).where(ChatMessage.session_id == other_session_id)
        ).first()
        foreign_id = str(foreign.id)

    resp = client.request(
        "DELETE",
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"message_ids": [foreign_id]},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_delete_missing_session_returns_404(admin_headers) -> None:
    """删除不存在的会话 404。"""
    resp = client.delete(f"/api/v1/chat/sessions/{uuid.uuid4()}", headers=admin_headers)
    assert resp.status_code == 404


def test_delete_deleted_session_returns_404(admin_headers) -> None:
    """重复删除 404：已删会话与不存在同态。"""
    resp = client.post("/api/v1/chat/sessions", headers=admin_headers)
    session_id = resp.json()["data"]["id"]
    assert (
        client.delete(
            f"/api/v1/chat/sessions/{session_id}", headers=admin_headers
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/v1/chat/sessions/{session_id}", headers=admin_headers
        ).status_code
        == 404
    )
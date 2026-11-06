"""阶段 2：解析任务服务测试（需 Postgres + seed；ARQ 入队以 mock 顶替）。

覆盖任务链路四个契约点：
  1. 先落库 pending 再入队（手动接口与上传回调两条入口）；
  2. 入队失败：任务标 failed 并写 error_summary，异常不阻断文档主流程；
  3. 任务的创建与查询都必须先过文档可见性（越权 404 语义）；
  4. worker 执行侧状态机：成功落 succeeded；失败按 PARSE_MAX_RETRY 决定
     抛回重试（保留 running）或耗尽落 failed。

注意：fixture 的 skip 只包造数阶段，测试体内的断言失败不会被吞成 skip。
"""

import asyncio
import uuid
from types import SimpleNamespace

import bcrypt
import pytest
from sqlalchemy import delete, select

from app.config import settings
from app.core.exceptions import NotFoundError
from app.database import SessionLocal
from app.models.ai_ext.parse_task import (
    PARSE_STATUS_FAILED,
    PARSE_STATUS_PENDING,
    PARSE_STATUS_RUNNING,
    PARSE_STATUS_SUCCEEDED,
    DocParseTask,
)
from app.models.system.dept import Dept
from app.models.system.doc import Doc, DocAudienceDept
from app.models.system.role import Role
from app.models.system.user import User, UserRole
from app.services.ai_ext import integration, parse_task_service
from app.services.system import doc_service
from app.workers import tasks as worker_tasks
from app.workers.tasks import parse_document
from scripts.seed import run_seed


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_doc(
    session,
    *,
    title: str,
    dept_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    audience_dept_ids: list[uuid.UUID],
) -> Doc:
    doc = Doc(
        title=title,
        dept_id=dept_id,
        original_filename=f"{title}.md",
        extension="md",
        size_bytes=100,
        storage_key=f"test/{uuid.uuid4()}.md",
        sha256="d" * 64,
        uploaded_by=uploaded_by,
        is_deleted=False,
    )
    session.add(doc)
    session.flush()
    for aid in audience_dept_ids:
        session.add(DocAudienceDept(doc_id=doc.id, dept_id=aid))
    return doc


def _setup(session, registry: dict) -> SimpleNamespace:
    """造数：staff 在 A 分支可读 doc_a；doc_b 归 B 分支对 staff 不可见。"""
    run_seed(session)
    session.commit()
    admin = session.scalar(select(User).where(User.username == "admin"))
    root = session.scalar(
        select(Dept).where(Dept.parent_id.is_(None), Dept.is_deleted.is_(False))
    )
    staff_role = session.scalar(
        select(Role).where(Role.code == "staff", Role.is_deleted.is_(False))
    )
    assert admin is not None and root is not None and staff_role is not None

    suffix = uuid.uuid4().hex[:8]
    branch_a = Dept(name=f"任务-A-{suffix}", parent_id=root.id, is_deleted=False)
    branch_b = Dept(name=f"任务-B-{suffix}", parent_id=root.id, is_deleted=False)
    session.add_all([branch_a, branch_b])
    session.flush()
    registry["dept_ids"] += [branch_a.id, branch_b.id]

    staff = User(
        username=f"pts_{suffix}",
        password_hash=_hash_password("pass"),
        dept_id=branch_a.id,
        is_deleted=False,
    )
    session.add(staff)
    session.flush()
    session.add(UserRole(user_id=staff.id, role_id=staff_role.id))
    registry["user_ids"] += [staff.id]

    doc_a = _create_doc(
        session,
        title=f"pt-doc-a-{suffix}",
        dept_id=branch_a.id,
        uploaded_by=admin.id,
        audience_dept_ids=[branch_a.id],
    )
    doc_b = _create_doc(
        session,
        title=f"pt-doc-b-{suffix}",
        dept_id=branch_b.id,
        uploaded_by=admin.id,
        audience_dept_ids=[branch_b.id],
    )
    registry["doc_ids"] += [doc_a.id, doc_b.id]
    session.commit()
    return SimpleNamespace(admin=admin, staff=staff, doc_a=doc_a, doc_b=doc_b)


def _cleanup(registry: dict) -> None:
    with SessionLocal() as session:
        for doc_id in registry["doc_ids"]:
            session.execute(delete(DocParseTask).where(DocParseTask.doc_id == doc_id))
            session.execute(
                delete(DocAudienceDept).where(DocAudienceDept.doc_id == doc_id)
            )
            session.execute(delete(Doc).where(Doc.id == doc_id))
        for user_id in registry["user_ids"]:
            session.execute(delete(UserRole).where(UserRole.user_id == user_id))
            session.execute(delete(User).where(User.id == user_id))
        for dept_id in registry["dept_ids"]:
            session.execute(delete(Dept).where(Dept.id == dept_id))
        session.commit()


@pytest.fixture
def pt_env():
    registry: dict = {"dept_ids": [], "user_ids": [], "doc_ids": []}
    session = SessionLocal()
    try:
        env = _setup(session, registry)
    except Exception as exc:
        session.close()
        _cleanup(registry)
        pytest.skip(f"PostgreSQL 或迁移未就绪，请先 compose up + upgrade head: {exc}")
    yield session, env
    session.close()
    _cleanup(registry)


def test_create_and_enqueue_persists_pending_task(pt_env, monkeypatch) -> None:
    """手动入口：任务先提交为 pending，再带着 task_id 入队。"""
    session, env = pt_env
    calls: list[uuid.UUID] = []
    monkeypatch.setattr(
        parse_task_service, "enqueue_parse_document", calls.append
    )

    # 方案 B：doc_a 的 audience 只覆盖 branch_a，对其可见的是子树内的 staff 而非超管
    task = parse_task_service.create_and_enqueue(
        session, user_id=env.staff.id, doc_id=env.doc_a.id
    )
    assert task.status == PARSE_STATUS_PENDING
    assert calls == [task.id]

    # 落库校验：不依赖会话缓存，重新查询任务行确实存在
    stored = session.execute(
        select(DocParseTask).where(DocParseTask.doc_id == env.doc_a.id)
    ).scalar_one()
    assert stored.id == task.id


def test_enqueue_failure_marks_task_failed(pt_env, monkeypatch) -> None:
    """入队失败：异常抛出，但任务已落库为 failed 且写入错误摘要（可观测）。"""
    session, env = pt_env

    def boom(task_id: uuid.UUID) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(parse_task_service, "enqueue_parse_document", boom)

    with pytest.raises(ConnectionError):
        parse_task_service.create_and_enqueue(
            session, user_id=env.staff.id, doc_id=env.doc_a.id
        )

    task = session.execute(
        select(DocParseTask).where(DocParseTask.doc_id == env.doc_a.id)
    ).scalar_one()
    assert task.status == PARSE_STATUS_FAILED
    assert task.error_summary is not None
    assert "入队失败" in task.error_summary


def test_upload_hook_creates_task_and_never_breaks_flow(pt_env, monkeypatch) -> None:
    """上传回调两条路：正常时自动建 pending 任务并入队；

    回调异常被底座吞掉不阻断上传，且失败任务仍落库为 failed 可观测。
    不依赖 main.py 是否已注册全局 hook（全量套件里会被其他测试导入）。
    """
    session, env = pt_env

    # 正常路径：直接调用装配函数，语义与底座通知一致
    calls: list[uuid.UUID] = []
    monkeypatch.setattr(
        parse_task_service, "enqueue_parse_document", calls.append
    )
    integration._on_doc_created(session, env.doc_a)
    task_a = session.execute(
        select(DocParseTask).where(DocParseTask.doc_id == env.doc_a.id)
    ).scalar_one()
    assert task_a.status == PARSE_STATUS_PENDING
    assert calls == [task_a.id]

    # 异常路径其一：入队炸 → 装配回调抛出，但任务已落库为 failed 可观测
    def boom(task_id: uuid.UUID) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(parse_task_service, "enqueue_parse_document", boom)
    with pytest.raises(ConnectionError):
        integration._on_doc_created(session, env.doc_b)
    tasks_b = session.execute(
        select(DocParseTask).where(DocParseTask.doc_id == env.doc_b.id)
    ).scalars().all()
    assert tasks_b, "入队失败也应留下任务行"
    assert all(t.status == PARSE_STATUS_FAILED for t in tasks_b)

    # 异常路径其二：底座通知里单个回调抛错只记日志，不阻断文档主流程；
    # 全套件下 main 注册的装配回调也在列表里，同样不得外抛
    def bad_hook(sess, doc):
        raise ConnectionError("hook broken")

    doc_service.register_doc_created_hook(bad_hook)
    try:
        doc_service._notify_doc_created(session, env.doc_b)  # 不应抛出
    finally:
        doc_service._doc_created_hooks.remove(bad_hook)


def test_task_read_and_create_require_doc_visibility(pt_env, monkeypatch) -> None:
    """越权即 404：staff 对不可见文档不能建任务，也查不到别人建的任务。"""
    session, env = pt_env
    monkeypatch.setattr(parse_task_service, "enqueue_parse_document", lambda tid: None)

    # 用系统内部入口（不校验可见性）为 doc_b 建任务，模拟 admin 侧已解析
    task = parse_task_service.enqueue_for_doc(session, doc_id=env.doc_b.id)

    with pytest.raises(NotFoundError):
        parse_task_service.create_and_enqueue(
            session, user_id=env.staff.id, doc_id=env.doc_b.id
        )
    with pytest.raises(NotFoundError):
        parse_task_service.get_task_for_user(
            session, user_id=env.staff.id, task_id=task.id
        )
    with pytest.raises(NotFoundError):
        parse_task_service.get_latest_for_doc(
            session, user_id=env.staff.id, doc_id=env.doc_b.id
        )

    # 可见但无任务 → None（doc_a 对 staff 可见，本用例未建过任务）
    assert (
        parse_task_service.get_latest_for_doc(
            session, user_id=env.staff.id, doc_id=env.doc_a.id
        )
        is None
    )


def _reload_task(task_id: uuid.UUID) -> DocParseTask:
    """worker 用自己的会话写库，这里新开短会话读终态，避免身份映射脏读。"""
    with SessionLocal() as s:
        task = s.get(DocParseTask, task_id)
        assert task is not None
        s.expunge(task)
        return task


def test_worker_success_marks_succeeded(pt_env, monkeypatch) -> None:
    """解析成功：running → succeeded。"""
    session, env = pt_env
    monkeypatch.setattr(parse_task_service, "enqueue_parse_document", lambda tid: None)
    task = parse_task_service.enqueue_for_doc(session, doc_id=env.doc_a.id)
    monkeypatch.setattr(worker_tasks, "ingest_document", lambda s, doc_id: 3)

    asyncio.run(parse_document({"job_try": 0}, str(task.id)))

    assert _reload_task(task.id).status == PARSE_STATUS_SUCCEEDED


def test_worker_failure_within_retry_budget_raises(pt_env, monkeypatch) -> None:
    """重试未耗尽：抛回异常交给 ARQ 重入队，任务保留 running 并记尝试次数。"""
    session, env = pt_env
    monkeypatch.setattr(parse_task_service, "enqueue_parse_document", lambda tid: None)
    monkeypatch.setattr(settings, "parse_max_retry", 1)
    task = parse_task_service.enqueue_for_doc(session, doc_id=env.doc_a.id)

    def boom(s, doc_id):
        raise ValueError("解析炸了")

    monkeypatch.setattr(worker_tasks, "ingest_document", boom)

    with pytest.raises(ValueError):
        asyncio.run(parse_document({"job_try": 0}, str(task.id)))

    reloaded = _reload_task(task.id)
    assert reloaded.status == PARSE_STATUS_RUNNING
    assert reloaded.error_summary is not None
    assert "将重试" in reloaded.error_summary


def test_worker_retry_exhausted_marks_failed(pt_env, monkeypatch) -> None:
    """重试耗尽（job_try 达到上限的最后一跑）：落 failed 并写错误摘要。"""
    session, env = pt_env
    monkeypatch.setattr(parse_task_service, "enqueue_parse_document", lambda tid: None)
    monkeypatch.setattr(settings, "parse_max_retry", 1)
    task = parse_task_service.enqueue_for_doc(session, doc_id=env.doc_a.id)

    def boom(s, doc_id):
        raise ValueError("解析又炸了")

    monkeypatch.setattr(worker_tasks, "ingest_document", boom)

    with pytest.raises(ValueError):
        asyncio.run(parse_document({"job_try": 1}, str(task.id)))

    reloaded = _reload_task(task.id)
    assert reloaded.status == PARSE_STATUS_FAILED
    assert reloaded.error_summary is not None
    assert "重试耗尽" in reloaded.error_summary

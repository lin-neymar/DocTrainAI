"""解析任务：创建入库 + 入队；按可见性查询状态。"""

from __future__ import annotations  # 开启延迟类型注解，支持模型互相引用

import uuid

from sqlalchemy import select  # SQLAlchemy查询构造器
from sqlalchemy.orm import Session  # 数据库会话

from app.core.exceptions import NotFoundError  # 自定义资源不存在异常
from app.models.ai_ext.parse_task import (
    PARSE_STATUS_FAILED,  # 任务失败状态
    PARSE_STATUS_PENDING,  # 任务待处理状态常量
    DocParseTask,  # 文档解析任务模型
)
from app.models.system.doc import Doc  # 文档主表模型
from app.services.ai_ext.queue import enqueue_parse_document  # ARQ任务入队方法
from app.services.system.scope_service import get_visible_doc_ids  # 获取当前用户有权限查看的文档ID


# 辅助函数：检查文档可见性
def _require_visible_doc(
    session:Session, *, user_id:uuid.UUID, doc_id:uuid.UUID
)-> Doc:
    visible = set(get_visible_doc_ids(session,user_id))
    if doc_id not in visible:
        raise NotFoundError("文档不存在")
    doc=session.get(Doc,doc_id)
    if doc is None or doc.is_deleted:
        raise NotFoundError("文档不存在")
    return doc

# 实现：核心流程——建 pending 任务落库后入队；入队失败回标 failed 并抛出
def _create_and_enqueue(session: Session, *, doc_id: uuid.UUID) -> DocParseTask:
    task = DocParseTask(doc_id=doc_id, status=PARSE_STATUS_PENDING)
    session.add(task)
    session.commit()
    session.refresh(task)

    # 先落库再入队，避免 worker 拿到 task_id 时任务行还没提交
    try:
        enqueue_parse_document(task.id)
    except Exception as exc:  # noqa: BLE001 — 入队失败：任务标记 failed 可观测
        task.status = PARSE_STATUS_FAILED
        task.error_summary = f"入队失败: {str(exc)[:500]}"
        session.commit()
        raise
    return task


# 实现：系统内部联动——为文档创建解析任务并入队（不校验可见性）
def enqueue_for_doc(session: Session, *, doc_id: uuid.UUID) -> DocParseTask:
    """上传后自动解析入口：调用上下文（上传流程）已保证文档归属，不重复校验。"""
    return _create_and_enqueue(session, doc_id=doc_id)


# 实现：用户手动触发——校验可见性后创建解析任务并入队
def create_and_enqueue(
    session: Session, *, user_id: uuid.UUID, doc_id: uuid.UUID
) -> DocParseTask:
    """创建 pending 任务并入队。需要调用方已具备 doc:read（路由层校验）。"""
    _require_visible_doc(session, user_id=user_id, doc_id=doc_id)
    return _create_and_enqueue(session, doc_id=doc_id)

# 按可见性查询解析任务
def get_task_for_user(
    session:Session, *, user_id:uuid.UUID, task_id:uuid.UUID
)-> DocParseTask:
    task = session.get(DocParseTask,task_id)
    if task is None:
        raise NotFoundError("解析任务不存在")
    _require_visible_doc(session,user_id=user_id,doc_id=task.doc_id)    
    return task

# 按可见性查询最新解析任务
def get_latest_for_doc(
    session:Session, *, user_id:uuid.UUID, doc_id:uuid.UUID
)-> DocParseTask | None:
    _require_visible_doc(session,user_id=user_id,doc_id=doc_id)
    return session.execute(
        select(DocParseTask)
        .where(DocParseTask.doc_id == doc_id)
        .order_by(DocParseTask.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
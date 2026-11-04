"""解析任务：创建入库 + 入队；按可见性查询状态。"""

from __future__ import annotations  # 开启延迟类型注解，支持模型互相引用

import uuid

from sqlalchemy import select  # SQLAlchemy查询构造器
from sqlalchemy.orm import Session  # 数据库会话

from app.core.exceptions import NotFoundError  # 自定义资源不存在异常
from app.models.ai_ext.parse_task import (
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

# 创建解析任务并入队
def create_and_enqueue(
    session:Session, *, user_id:uuid.UUID, doc_id:uuid.UUID
)-> DocParseTask:
    """创建 pending 任务并入队。需要调用方已具备 doc:read（路由层校验）。"""
    _require_visible_doc(session,user_id=user_id,doc_id=doc_id)

    task = DocParseTask(doc_id=doc_id,status=PARSE_STATUS_PENDING)
    session.add(task)
    session.commit()
    session.refresh(task)

    # 先落库再入队，避免 worker 找不到 task 行
    enqueue_parse_document(task.id)
    return task

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
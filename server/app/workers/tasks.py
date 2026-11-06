"""ARQ 任务函数：推进解析任务状态机（pending → running → succeeded/failed）。

失败处理按 PARSE_MAX_RETRY 配置：次数未耗尽时抛回异常，由 ARQ 重入队重试
（WorkerSettings.max_tries）；耗尽后才落 failed 并写错误摘要。
"""
from __future__ import annotations  # 开启延迟类型注解

import logging  # 日志模块
import uuid  # UUID转换

import app.models.ai_ext  # noqa: F401  — 注册 doc_parse_task / doc_chunk
import app.models.system  # noqa: F401  — Worker 进程需注册 doc 等表，解析 FK
from app.config import settings  # 读取 PARSE_MAX_RETRY
from app.database import SessionLocal  # 数据库会话工厂
from app.models.ai_ext.parse_task import (
    PARSE_STATUS_FAILED,  # 任务失败状态
    PARSE_STATUS_RUNNING,  # 任务运行中状态
    PARSE_STATUS_SUCCEEDED,  # 任务成功状态
    DocParseTask,  # 解析任务ORM模型
)
from app.services.ai_ext.parse_pipeline import ingest_document  # 解析流水线

logger = logging.getLogger(__name__)


async def parse_document(ctx: dict, task_id: str) -> None:
    """解析一篇文档：running → succeeded；失败按配置重试，耗尽才 failed。

    ctx["job_try"] 由 ARQ 注入（首次执行 = 0）；抛回的异常触发 ARQ 重入队。
    """
    tid = uuid.UUID(task_id)  # 字符串task_id转UUID
    session = SessionLocal()  # 获取数据库会话
    try:
        task = session.get(DocParseTask, tid)
        if task is None:
            logger.error("parse task not found: %s", task_id)
            return
        task.status = PARSE_STATUS_RUNNING  # 更新为运行中（重试轮也会重置回 running）
        task.error_summary = None
        session.commit()

        try:
            chunk_count = ingest_document(session, doc_id=task.doc_id)
        except Exception as exc:  # noqa: BLE001 — Worker 边界：区分可重试与终态失败
            session.rollback()
            # job_try 是已完成的重试次数：0=首跑；小于上限说明后面还有一次机会
            will_retry = ctx.get("job_try", 0) < settings.parse_max_retry
            note = f"第 {ctx.get('job_try', 0) + 1} 次尝试失败"
            tail = "（将重试）" if will_retry else "（重试耗尽）"
            task.error_summary = f"{note}{tail}: {exc}"[:500]
            if will_retry:
                session.commit()  # 保留 running，等 ARQ 重入队再跑一轮
                raise
            task.status = PARSE_STATUS_FAILED  # 次数耗尽，落终态
            session.commit()
            logger.exception("parse task failed after retries: %s", task_id)
            raise
        task.status = PARSE_STATUS_SUCCEEDED
        session.commit()
        logger.info(
            "parse task succeeded: task=%s doc=%s chunks=%d",
            task_id, task.doc_id, chunk_count,
        )
    finally:
        session.close() # 关闭数据库会话

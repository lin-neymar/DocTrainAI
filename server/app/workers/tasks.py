"""ARQ 任务函数：推进解析任务状态机（pending → running → succeeded/failed）。

失败处理按 PARSE_MAX_RETRY 配置：ARQ 0.28 起任务抛普通异常不再自动重入队，
剩余次数内需显式抛 Retry(defer) 触发重试；耗尽后才落 failed 并写错误摘要。
ctx["job_try"] 由 ARQ 注入，0.28 语义下首次执行 = 1。
"""
from __future__ import annotations  # 开启延迟类型注解

import logging  # 日志模块
import uuid  # UUID转换

from arq.worker import Retry  # ARQ 0.28：显式抛 Retry 才重入队

import app.models.ai_ext  # noqa: F401  — 注册 doc_parse_task / doc_chunk
import app.models.system  # noqa: F401  — Worker 进程需注册 doc 等表，解析 FK
from app.config import settings  # 读取 PARSE_MAX_RETRY
from app.core.logging import job_id_var  # worker 日志关联 job_id
from app.database import SessionLocal  # 数据库会话工厂
from app.models.ai_ext.parse_task import (
    PARSE_STATUS_FAILED,  # 任务失败状态
    PARSE_STATUS_RUNNING,  # 任务运行中状态
    PARSE_STATUS_SUCCEEDED,  # 任务成功状态
    DocParseTask,  # 解析任务ORM模型
)
from app.services.ai_ext.parse_pipeline import ingest_document  # 解析流水线

logger = logging.getLogger(__name__)

# 重试前等待秒数：给上游 embedding/解析的瞬时抖动留恢复窗口
RETRY_DEFER_SECONDS = 5.0


async def parse_document(ctx: dict, task_id: str) -> None:
    """解析一篇文档：running → succeeded；失败按配置重试，耗尽才 failed。

    ctx["job_try"] 由 ARQ 注入（0.28 首次执行 = 1）；剩余次数内抛 Retry，
    ARQ 将任务重新入队；耗尽后落 failed 并抛出原始异常由 ARQ 记录。
    """
    # 阶段 4：绑定 ARQ job_id 到 contextvar；重试轮次 job_id 不变，全部日志可串起来
    job_token = job_id_var.set(str(ctx.get("job_id") or "-"))
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
            # 0.28 首跑 job_try=1；None/0 兜底按首跑处理
            job_try = int(ctx.get("job_try") or 1)
            will_retry = job_try < settings.parse_max_retry + 1
            note = f"第 {job_try} 次尝试失败"
            tail = "（将重试）" if will_retry else "（重试耗尽）"
            task.error_summary = f"{note}{tail}: {exc}"[:500]
            if will_retry:
                session.commit()  # 保留 running，抛 Retry 由 ARQ 重入队
                raise Retry(defer=RETRY_DEFER_SECONDS) from exc
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
        job_id_var.reset(job_token)  # 释放绑定，避免串到下一个 job
        session.close() # 关闭数据库会话

"""ARQ 任务函数。S3：只推进解析任务状态机；S4 再接真实解析。"""
from __future__ import annotations  # 开启延迟类型注解

import logging  # 日志模块
import uuid  # UUID转换

import app.models.ai_ext  # noqa: F401  — 注册 doc_parse_task / doc_chunk
import app.models.system  # noqa: F401  — Worker 进程需注册 doc 等表，解析 FK
from app.database import SessionLocal  # 数据库会话工厂
from app.models.ai_ext.parse_task import (
    PARSE_STATUS_FAILED,  # 任务失败状态
    PARSE_STATUS_RUNNING,  # 任务运行中状态
    PARSE_STATUS_SUCCEEDED,  # 任务成功状态
    DocParseTask,  # 解析任务ORM模型
)

# ----- S4：真实解析流水线 —— 读原件 → 切分 → Embedding → jieba/tsvector 写入 -----
from app.services.ai_ext.parse_pipeline import ingest_document

logger = logging.getLogger(__name__)

async def parse_document(ctx: dict, task_id: str) -> None:
    """占位解析：pending 之后的 running → succeeded。
    ctx 由 ARQ 注入；业务只用 task_id。
    """
    tid = uuid.UUID(task_id)  # 字符串task_id转UUID
    session = SessionLocal()  # 获取数据库会话
    try:
        task = session.get(DocParseTask, tid)
        if task is None:
            logger.error("parse task not found: %s", task_id)
            return
        task.status = PARSE_STATUS_RUNNING  # 更新为运行中
        task.error_summary = None
        session.commit()

        # S4：真实解析流水线 —— 读原件 → 切分 → Embedding → jieba/tsvector 写入
        chunk_count = ingest_document(session, doc_id=task.doc_id)

        task.status = PARSE_STATUS_SUCCEEDED
        session.commit()
        logger.info(
            "parse task succeeded: task=%s doc=%s chunks=%d",
            task_id, task.doc_id, chunk_count,
        )
    except Exception as exc:  # noqa: BLE001 — Worker 边界：记入任务失败摘要
        session.rollback()  # 异常回滚事务
        task = session.get(DocParseTask, tid)
        if task is not None:
            task.status = PARSE_STATUS_FAILED  # 标记失败
            task.error_summary = str(exc)[:500] # 截取错误信息
            session.commit()
        logger.exception("parse task failed: %s", task_id)
    finally:
        session.close() # 关闭数据库会话
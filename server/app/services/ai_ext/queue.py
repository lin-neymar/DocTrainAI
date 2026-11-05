"""ARQ 入队（仅 Redis；不存业务正文）。

封装文档解析任务的入队逻辑：上传后把解析任务丢进 ARQ 队列交给 Worker。

同步接口自适应两种调用上下文：
  - 普通线程（FastAPI 同步端点跑在线程池）：直接 asyncio.run；
  - 事件循环线程（async 端点的同步调用链）：改用新线程执行，
    避免 "asyncio.run() cannot be called from a running event loop"。
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Coroutine

from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings

# Worker 里注册的同名函数
PARSE_DOCUMENT_JOB = "parse_document"


# 解析文档任务入队函数
async def _enqueue_parse_document(task_id: uuid.UUID) -> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await redis.enqueue_job(PARSE_DOCUMENT_JOB, str(task_id))
    finally:
        await redis.aclose()


# 实现：在无事件循环的新线程里执行协程，同步等待并把异常透传给调用线程
def _run_in_new_thread(coro: Coroutine[None, None, None]) -> None:
    holder: list[BaseException | None] = [None]

    def _runner() -> None:
        try:
            asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 — 异常透传，由调用方处理
            holder[0] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if holder[0] is not None:
        raise holder[0]


# 实现：供同步 service 调用的入队入口（自适应有无运行中的事件循环）
def enqueue_parse_document(task_id: uuid.UUID) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # 当前线程无事件循环（线程池里的同步端点）：直接跑
        asyncio.run(_enqueue_parse_document(task_id))
    else:
        # 当前线程已有事件循环（async 端点的同步调用链）：借新线程执行
        _run_in_new_thread(_enqueue_parse_document(task_id))
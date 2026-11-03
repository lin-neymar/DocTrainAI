"""ARQ 入队（仅 Redis；不存业务正文）。
   封装**文档解析异步任务的入队逻辑**：当用户上传文档后，调用这个函数，把解析、分片、向量化任务丢进 ARQ 队列交给后台 Worker 慢慢跑；
   **专门解决同步 FastAPI 路由调用异步 ARQ 的兼容问题**。
"""

from __future__ import annotations  # 开启延迟类型注解，支持模型互相引用

import asyncio  # Python异步IO核心库
import uuid     # 生成唯一标识ID

from arq import create_pool              # 创建ARQ Redis连接池
from arq.connections import RedisSettings # ARQ的Redis连接配置类

from app.config import settings  # 读取项目全局环境配置

# Worker 里注册的同名函数
PARSE_DOCUMENT_JOB = "parse_document"

# 解析文档任务入队函数
async def _enqueue_parse_document(task_id:uuid.UUID)-> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url)) # 创建Redis连接池
    try:
        await redis.enqueue_job(PARSE_DOCUMENT_JOB,str(task_id)) # 入队解析任务
    finally:
        await redis.aclose() # 关闭连接池

# 实现：供同步 service 调用；FastAPI sync 路由跑在线程里，可用 asyncio.run
def enqueue_parse_document(task_id:uuid.UUID)-> None:
    asyncio.run(_enqueue_parse_document(task_id)) # 异步执行入队操作
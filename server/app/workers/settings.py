"""ARQ Worker 配置入口。
启动（在 server/ 下）：
  .venv/bin/arq app.workers.settings.WorkerSettings
"""
from arq.connections import RedisSettings

from app.config import settings
from app.core.logging import setup_logging
from app.workers.tasks import parse_document

# 阶段 4：worker 进程与 api 同款结构化日志（text/json 随 LOG_FORMAT；幂等）
setup_logging(settings.effective_log_format)

class WorkerSettings:
    functions = [parse_document]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    # 任务函数抛异常时 ARQ 重入队的总尝试上限：首跑 1 次 + PARSE_MAX_RETRY 次重试
    max_tries = settings.parse_max_retry + 1
    # 阶段 4：解析任务最大并发（PARSE_MAX_JOBS，默认 2，适配 2C4G 服务器）
    max_jobs = settings.parse_max_jobs
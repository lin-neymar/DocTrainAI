"""ARQ Worker 配置入口。
启动（在 server/ 下）：
  .venv/bin/arq app.workers.settings.WorkerSettings
"""
from arq.connections import RedisSettings

from app.config import settings
from app.workers.tasks import parse_document


class WorkerSettings:
    functions = [parse_document]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    # 任务函数抛异常时 ARQ 重入队的总尝试上限：首跑 1 次 + PARSE_MAX_RETRY 次重试
    max_tries = settings.parse_max_retry + 1
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
    # 可按需加 max_jobs、job_timeout；阶段 2 后续再配置化重试次数
"""Alembic 迁移运行时配置（G5）。

每次执行 alembic upgrade / revision 都会先跑这个文件：
  1. 从 app.config 读 DATABASE_URL（与 FastAPI 同一套 .env）
  2. 加载 ORM 模型，让 autogenerate 能对比「模型 vs 数据库」
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.models.system  # noqa: F401  副作用：注册 Dept 等模型到 Base.metadata
from alembic import context
from app.config import settings
from app.database import Base

config = context.config
# 覆盖 alembic.ini 里的占位 URL，避免把真实密码写进 ini 文件
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic 靠这个 metadata 知道「应该有哪些表」
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL 文本，不连库（少用）。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连上 Postgres 执行迁移（日常用这个）。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

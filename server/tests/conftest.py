"""pytest 全局装配：把整个测试会话切到独立测试库，与开发库彻底隔离。

原理（模块级代码，先于任何测试模块导入 app.*，因此 engine/Settings 创建时已指向测试库）：
  1. 测试库连接串取 TEST_DATABASE_URL（真实环境变量 > .env），缺省由开发库名 + "_test"。
  2. 连维护库幂等 CREATE DATABASE；连测试库 DROP SCHEMA public 重建——每次会话全量重置。
  3. os.environ 覆盖 DATABASE_URL 与 FILE_STORAGE_DIR（后者指到 server/.pytest_storage，
     测试上传的文件不再落进开发存储目录）。
  4. 程序化 alembic upgrade head：测试库结构与开发/生产完全一致（含 pgvector 迁移）。

Postgres 未启动时这里不炸会话：仅打印提示，DB 集成测试仍按各自 fixture 的 skip 逻辑降级。
"""

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = SERVER_DIR.parent


def _env_first(*keys: str) -> str:
    """按 pydantic-settings 同款优先级取值：真实环境变量 > 仓库 .env。"""
    file_values = dotenv_values(ROOT_DIR / ".env")
    for key in keys:
        value = os.environ.get(key) or file_values.get(key)
        if value:
            return str(value)
    return ""


def _derive_test_url(dev_url: str) -> str:
    """开发库名追加 _test：postgresql+psycopg://…/doctrain → …/doctrain_test。"""
    from sqlalchemy.engine import make_url

    url = make_url(dev_url)
    return url.set(database=f"{url.database}_test").render_as_string(
        hide_password=False
    )


def _ensure_database(test_url: str) -> None:
    """幂等建库 + 每次会话重置 public schema（AUTOCOMMIT：CREATE DATABASE 不能进事务）。"""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    maintenance = create_engine(
        make_url(test_url).set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    try:
        dbname = str(make_url(test_url).database or "")
        with maintenance.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}
            ).scalar()
            if not exists:
                # 库名来自受控派生规则（无引号标识符），不支持参数化，只放行安全字符
                if not dbname.replace("_", "").replace("-", "").isalnum():
                    raise RuntimeError(f"非法测试库名: {dbname}")
                conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    finally:
        maintenance.dispose()

    target = create_engine(test_url, isolation_level="AUTOCOMMIT")
    try:
        with target.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            # pgvector 镜像自带扩展文件；DROP SCHEMA 会连带删掉扩展，这里补回
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    finally:
        target.dispose()


def _upgrade_head(test_url: str) -> None:
    """程序化跑迁移，保证测试库 schema 与迁移链一致（而非模型 create_all 近似）。"""
    from alembic.config import Config

    from alembic import command

    # env.py 会 import app.*，需保证 server/ 在模块搜索路径上
    if str(SERVER_DIR) not in sys.path:
        sys.path.insert(0, str(SERVER_DIR))

    cfg = Config()
    cfg.set_main_option("config_file_name", str(SERVER_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVER_DIR / "alembic"))
    cfg.set_main_option("prepend_sys_path", str(SERVER_DIR))
    command.upgrade(cfg, "head")


def _bootstrap() -> None:
    dev_url = _env_first("DATABASE_URL")
    if not dev_url:
        raise RuntimeError("缺少 DATABASE_URL，无法确定测试库")
    test_url = _env_first("TEST_DATABASE_URL") or _derive_test_url(dev_url)

    _ensure_database(test_url)

    # 关键：必须在 app.config / app.database 首次导入之前覆盖环境
    os.environ["DATABASE_URL"] = test_url
    storage_dir = SERVER_DIR / ".pytest_storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    os.environ["FILE_STORAGE_DIR"] = str(storage_dir)

    _upgrade_head(test_url)
    print(f"pytest → 测试库 {test_url.split('://')[0]}://***@（schema 已重置并 upgrade head）")


try:
    _bootstrap()
except Exception as exc:  # noqa: BLE001 — 装配失败不阻断会话，DB 用例各自 skip
    print(f"pytest 测试库准备失败（{exc}）；依赖数据库的用例将降级为 skip")

#!/bin/sh
# 阶段 4：api 容器启动入口。
# 职责：先执行 alembic upgrade head，再执行幂等 seed，成功后才启动应用进程。
# worker 容器以「首参 worker」复用本入口：跳过迁移与 seed
# （worker 不碰 schema，见 SERVER_SPEC 阶段 4 契约）。
set -e

if [ "${1:-}" = "worker" ]; then
    shift
else
    echo "[entrypoint] alembic upgrade head"
    alembic upgrade head

    echo "[entrypoint] seed（幂等：已存在的种子数据自动跳过）"
    python scripts/seed.py
fi

echo "[entrypoint] exec: $*"
exec "$@"
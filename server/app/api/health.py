"""健康检查路由（无需登录）。

供负载均衡、Docker 探针或本地确认进程存活；响应格式与 PROJECT_SPEC 统一体一致。
"""

from fastapi import APIRouter

from app.core.response import success

router = APIRouter(tags=["health"])


@router.get("/health", summary="健康检查", description="不需要登录，用于确认服务进程可用。")
def health() -> dict:
    # data 只表示进程存活；不查库，避免把 DB 故障误报成「服务 down」
    return success({"status": "up"})

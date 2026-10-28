"""健康检查路由（无需登录）。

供负载均衡、Docker 探针或本地确认进程存活；响应格式与 PROJECT_SPEC 统一体一致。
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="健康检查", description="不需要登录，用于确认服务进程可用。")
def health() -> dict:
    return {"code": 0, "message": "ok", "data": {"status": "up"}}

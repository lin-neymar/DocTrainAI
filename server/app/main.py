"""FastAPI 应用入口。

职责：创建 app 实例、挂载各 APIRouter、注册全局中间件/异常处理（后续阶段补充）。
启动：在 server/ 目录执行 uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.config import settings

app = FastAPI(title="DocTrainAI", version="0.1.0")
app.include_router(health_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root() -> dict:
    """根路径探活：返回当前 APP_ENV，便于确认配置是否加载。"""
    return {"code": 0, "message": "ok", "data": {"app_env": settings.app_env}}

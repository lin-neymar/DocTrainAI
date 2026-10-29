"""FastAPI 应用入口。

职责：创建 app 实例、挂载各 APIRouter、注册全局异常处理。
启动：在 server/ 目录执行 uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.system.auth import router as auth_router
from app.config import settings
from app.core.handlers import register_exception_handlers
from app.core.response import success

app = FastAPI(title="DocTrainAI", version="0.1.0")
# 先注册异常处理，再挂路由，保证所有 endpoint 都走统一 { code, message, data }
register_exception_handlers(app)

# D-C：浏览器从 Vite 等「不同 Origin」访问 API 时，必须显式允许，否则预检/响应会被拦。
# allow_credentials=True：以后若前端带 Cookie 或部分跨域场景需要；当前 JWT 在 Authorization 头里。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
# 实现：根路径探活，返回当前 APP_ENV
def root() -> dict:
    """根路径探活：返回当前 APP_ENV，便于确认配置是否加载。"""
    return success({"app_env": settings.app_env})

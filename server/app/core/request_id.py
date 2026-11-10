"""request_id 中间件与结构化访问日志（阶段 4）。

每个 HTTP 请求：生成 UUID4 → 写入 contextvar → 响应头 X-Request-ID 回传；
请求结束时输出一条访问日志（method/path/status/duration_ms/request_id）。
未预期异常在传播链上不重置 contextvar，保证 500 留痕仍能关联 request_id。
"""

import logging
import sys
import time
import uuid

from starlette.datastructures import MutableHeaders

from app.core.logging import request_id_var

access_logger = logging.getLogger("app.access")


class RequestIDMiddleware:
    """纯 ASGI 中间件（比 BaseHTTPMiddleware 更稳：不改变 SSE 等流式响应行为）。"""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started_at = time.perf_counter()
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
            access_logger.info(
                "%s %s -> %s in %.1fms",
                scope["method"],
                scope["path"],
                status_code,
                duration_ms,
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status_code,
                    "duration_ms": duration_ms,
                    "request_id": request_id,
                },
            )
            # 异常仍在传播（未预期 500 尚未被最外层 ServerErrorMiddleware 记录）时不重置，
            # 让 500 的 ERROR 日志也能带上 request_id；任务上下文结束即回收，不会串请求
            if sys.exc_info()[0] is None:
                request_id_var.reset(token)
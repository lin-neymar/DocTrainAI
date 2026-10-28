"""全局异常 → 统一 JSON 响应。

FastAPI 默认返回 {"detail": "..."}；此处全部改为 { code, message, data }，
与前端、pytest 的断言约定一致。
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

# SERVER_SPEC：403/404/409 等预期拒绝不打印堆栈，避免日志噪音
_QUIET_HTTP_STATUSES = frozenset({403, 404, 409})


def _error_body(*, code: int, message: str, data: Any = None) -> dict[str, Any]:
    """失败响应与成功体字段相同，仅 code ≠ 0。"""
    return {"code": code, "message": message, "data": data}


def register_exception_handlers(app: FastAPI) -> None:
    """在 main 里创建 app 后、挂载路由前调用一次。

    多个 handler 按异常类型匹配；最宽的类型 Exception 只兜未预料的错误。
    """

    @app.exception_handler(AppException)
    def handle_app_exception(_request: Request, exc: AppException) -> JSONResponse:
        # 仅当子类误配成 5xx 时才记日志；常规 401–409 静默返回
        if exc.http_status not in _QUIET_HTTP_STATUSES and exc.http_status >= 500:
            logger.exception("AppException: %s", exc.message)
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_body(code=exc.code, message=exc.message, data=None),
        )

    @app.exception_handler(RequestValidationError)
    def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic / FastAPI 入参校验失败 → HTTP 422，code 42200
        return JSONResponse(
            status_code=422,
            content=_error_body(
                code=42200,
                message="validation failed",
                data={"errors": exc.errors()},  # 字段级错误，供前端表单展示
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    def handle_http_exception(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # 框架层 HTTPException：未知路由 404、依赖里 raise HTTPException 等
        status = exc.status_code
        code_by_status: dict[int, int] = {
            401: 40100,
            403: 40300,
            404: 40400,
            409: 40900,
            422: 42200,
        }
        # 未在表中的状态：5xx 统一 50000；其它按 status*100 凑业务码
        code = code_by_status.get(status, 50000 if status >= 500 else status * 100)
        detail = exc.detail
        if isinstance(detail, str):
            message = detail
        else:
            message = "request failed"
        return JSONResponse(
            status_code=status,
            content=_error_body(code=code, message=message, data=None),
        )

    @app.exception_handler(Exception)
    def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        # 最后一道防线：不向客户端泄露内部异常信息
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_error_body(code=50000, message="internal server error", data=None),
        )

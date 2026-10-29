"""横切能力包（core）。

当前：统一成功体 success、业务异常类、register_exception_handlers。
后续 JWT / get_current_user / require_permission 也会放在此目录。
对外 re-export 常用符号，业务代码可 from app.core import NotFoundError, success。
"""

from app.core.exceptions import (
    AppException,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationFailedError,
)
from app.core.handlers import register_exception_handlers
from app.core.response import success

__all__ = [
    "AppException",
    "ConflictError",
    "ForbiddenError",
    "NotFoundError",
    "UnauthorizedError",
    "ValidationFailedError",
    "register_exception_handlers",
    "success",
]

"""业务侧「预期内失败」异常。

路由 / service 只 raise 子类，不写 JSONResponse。
全局 handlers 会按 PROJECT_SPEC 转成 { code, message, data } 并设置 HTTP 状态码。

对照表（节选）：
  401 → 40100 未登录或令牌无效
  403 → 40300 已登录但无权限
  404 → 40400 资源不存在
  409 → 40900 业务冲突（重名、有下级时删除等）
  422 → 42200 参数或校验失败（含上传扩展名/文件头/大小）
"""


class AppException(Exception):
    """预期内失败的基类。

    子类用类属性固定 http_status、code；message 可在构造时覆盖为更具体的文案。
    业务代码不要直接 raise AppException，用下面的具名子类。
    """

    http_status: int = 500
    code: int = 50000
    default_message: str = "internal server error"

    def __init__(self, message: str | None = None) -> None:
        # 不传 message 时用子类的 default_message（如 ConflictError → "conflict"）
        self.message = message if message is not None else self.default_message
        super().__init__(self.message)


class UnauthorizedError(AppException):
    """JWT 缺失、过期或无效时（阶段 D 鉴权依赖会用到）。"""

    http_status = 401
    code = 40100
    default_message = "unauthorized"


class ForbiddenError(AppException):
    """已登录但缺少所需权限码（require_permission 会用到）。"""

    http_status = 403
    code = 40300
    default_message = "forbidden"


class NotFoundError(AppException):
    """资源不存在，或故意用 404 隐藏无权访问的资源（如不可见文档）。"""

    http_status = 404
    code = 40400
    default_message = "not found"


class ConflictError(AppException):
    """违反业务不变量：用户名重名、部门仍有子节点/用户时删除等。"""

    http_status = 409
    code = 40900
    default_message = "conflict"


class ValidationFailedError(AppException):
    """业务侧参数/文件校验失败（与 Pydantic 422 同码，便于前端统一处理）。"""

    http_status = 422
    code = 42200
    default_message = "validation failed"

"""成功响应封装。

PROJECT_SPEC 规定成功时：HTTP 200，body 为 { "code": 0, "message": "ok", "data": ... }。
路由 return success(...) 即可，不必手写 dict。
"""

from typing import Any


def success(data: Any = None, *, message: str = "ok") -> dict[str, Any]:
    """构造统一成功体。

    data：业务载荷；无内容时可省略（data 为 null）。
    message：一般保持 "ok"，仅在少数接口需要提示文案时改写。
    """
    return {"code": 0, "message": message, "data": data}

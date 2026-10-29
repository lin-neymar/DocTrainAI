"""F0：跨业务共用的请求/响应 Schema（分页等）。

PROJECT_SPEC：分页 data 固定为 { items, total, page, page_size }。
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageQuery(BaseModel):
    """列表接口查询参数：page 从 1 起；page_size 默认 20、最大 100。"""

    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数，最大 100")


class PageResult(BaseModel, Generic[T]):
    """列表接口 data 载荷形状（再包进 success(...)）。"""

    items: list[T]
    total: int
    page: int
    page_size: int


# 实现：把分页结果打成规约规定的 dict（items 可为已序列化的 dict 列表）
def page_data(
    *,
    items: list[Any],
    total: int,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

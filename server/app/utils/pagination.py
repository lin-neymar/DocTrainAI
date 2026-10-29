"""F0：分页计算小工具（SQL offset/limit 用）。"""


# 实现：把「第几页」转成 SQL OFFSET
def page_offset(page: int, page_size: int) -> int:
    """page 从 1 开始；非法值由 PageQuery 校验，此处假定已合法。"""
    return (page - 1) * page_size

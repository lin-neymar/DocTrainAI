"""HTTP 路由层（APIRouter）。

按模块拆分：当前仅有 health；阶段 1 起增加 api/system（auth、dept、user 等）。
路由层只做参数接收、Depends 鉴权、调用 service、返回 Schema，不写复杂 SQL。
"""

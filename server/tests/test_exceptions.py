"""统一异常与响应体的集成测试。

使用独立 mini FastAPI（不往 app.main 挂测试路由），避免污染正式路由表。
最后一条用例才测 main app，验证「未知路径」也走统一 404 体。
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.exceptions import ConflictError, NotFoundError
from app.core.handlers import register_exception_handlers
from app.core.response import success


def _build_client() -> TestClient:
    """构造带 handlers 的临时 app，并注册会触发各类异常的假路由。"""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/biz-not-found")
    def biz_not_found() -> dict:
        raise NotFoundError("部门不存在")

    @app.get("/biz-conflict")
    def biz_conflict() -> dict:
        raise ConflictError()

    @app.get("/boom")
    def boom() -> dict:
        raise RuntimeError("unexpected")

    class ItemCreate(BaseModel):
        name: str

    @app.post("/validate")
    def validate_item(_body: ItemCreate) -> dict:
        return success({"ok": True})

    # TestClient 默认 raise_server_exceptions=True，500 会直接抛到测试里；
    # 这里需要断言 JSON body，必须设为 False。
    return TestClient(app, raise_server_exceptions=False)


client = _build_client()


def test_success_helper_shape() -> None:
    assert success({"x": 1}) == {"code": 0, "message": "ok", "data": {"x": 1}}


def test_app_exception_not_found() -> None:
    response = client.get("/biz-not-found")

    assert response.status_code == 404
    assert response.json() == {
        "code": 40400,
        "message": "部门不存在",
        "data": None,
    }


def test_app_exception_conflict() -> None:
    response = client.get("/biz-conflict")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == 40900
    assert body["message"] == "conflict"
    assert body["data"] is None


def test_validation_error_unified_body() -> None:
    # 空 body 触发 Pydantic 必填校验 → 422 / 42200
    response = client.post("/validate", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 42200
    assert body["message"] == "validation failed"
    assert "errors" in body["data"]


def test_unhandled_exception_returns_500() -> None:
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "code": 50000,
        "message": "internal server error",
        "data": None,
    }


def test_unknown_route_unified_404() -> None:
    from app.main import app as main_app

    main_client = TestClient(main_app)
    response = main_client.get("/api/v1/no-such-route")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == 40400
    assert body["data"] is None

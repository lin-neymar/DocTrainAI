"""阶段 4：request_id 中间件与访问日志测试。

使用独立 mini FastAPI（不往 app.main 挂测试路由），与 test_exceptions.py 同风格。
"""

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.handlers import register_exception_handlers
from app.core.request_id import RequestIDMiddleware


def _build_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ok")
    def ok() -> dict:
        return {"status": "up"}

    @app.get("/boom")
    def boom() -> dict:
        raise RuntimeError("unexpected")

    return TestClient(app, raise_server_exceptions=False)


client = _build_client()


def test_request_id_header_unique_per_request() -> None:
    first = client.get("/ok")
    second = client.get("/ok")

    assert first.headers.get("x-request-id")
    assert second.headers.get("x-request-id")
    assert len(first.headers["x-request-id"]) == 32  # uuid4().hex
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


def test_request_id_header_present_on_500() -> None:
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.headers.get("x-request-id")


def test_access_log_fields(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get("/ok")

    records = [r for r in caplog.records if r.name == "app.access"]
    assert len(records) == 1
    record = records[0]
    assert record.method == "GET"
    assert record.path == "/ok"
    assert record.status == 200
    assert record.duration_ms >= 0
    assert record.request_id  # extra 显式附带，不依赖 formatter


def test_unexpected_500_logged_with_traceback(caplog) -> None:
    with caplog.at_level(logging.ERROR, logger="app.core.handlers"):
        client.get("/boom")

    records = [r for r in caplog.records if r.name == "app.core.handlers"]
    assert records
    assert records[0].exc_info  # traceback 留痕
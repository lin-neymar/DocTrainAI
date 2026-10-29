"""D-C：CORS 中间件 smoke（浏览器联调前置，curl 不带 Origin 时不触发 CORS 头）。"""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_cors_reflects_allowed_origin_on_health() -> None:
    origin = settings.cors_origin_list[0]
    response = client.get("/api/v1/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_cors_preflight_options() -> None:
    origin = settings.cors_origin_list[0]
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin

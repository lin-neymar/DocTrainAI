"""健康检查接口的自动化测试。

使用 TestClient 不占用端口即可请求 app；后续登录、越权等测试同目录扩展。
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_unified_response() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"code": 0, "message": "ok", "data": {"status": "up"}}

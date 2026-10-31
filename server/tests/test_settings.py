"""系统品牌与个人主题（SET）集成测试。"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from scripts.seed import run_seed

client = TestClient(app)


def _ensure_seeded() -> None:
    with SessionLocal() as session:
        run_seed(session)
        session.commit()


def _admin_headers() -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.init_admin_username,
            "password": settings.init_admin_password,
        },
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    try:
        _ensure_seeded()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")
    return _admin_headers()


def test_public_brand_readable_without_token() -> None:
    try:
        _ensure_seeded()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")

    resp = client.get("/api/v1/system/brand")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["site_name"]
    assert "login_subtitle" in data
    assert "has_logo" in data


def test_admin_update_brand_and_theme(admin_headers: dict[str, str]) -> None:
    put = client.put(
        "/api/v1/system/settings",
        headers=admin_headers,
        json={
            "site_name": "DocTrainAI测试",
            "login_subtitle": "验收副文案",
        },
    )
    assert put.status_code == 200
    assert put.json()["data"]["site_name"] == "DocTrainAI测试"

    theme = client.put(
        "/api/v1/auth/me/theme",
        headers=admin_headers,
        json={"theme_primary": "#224466"},
    )
    assert theme.status_code == 200
    assert theme.json()["data"]["theme_primary"] == "#224466"

    me = client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    assert me.json()["data"]["theme_primary"] == "#224466"

    # 恢复默认品牌文案，避免污染后续手工联调观感
    client.put(
        "/api/v1/system/settings",
        headers=admin_headers,
        json={
            "site_name": "DocTrainAI",
            "login_subtitle": "企业内部规章培训与知识助手",
        },
    )


def test_settings_requires_permission() -> None:
    try:
        _ensure_seeded()
    except Exception as exc:
        pytest.skip(f"PostgreSQL 或迁移未就绪: {exc}")

    assert client.get("/api/v1/system/settings").status_code == 401
    assert client.put(
        "/api/v1/system/settings",
        json={"site_name": "x", "login_subtitle": "y"},
    ).status_code == 401

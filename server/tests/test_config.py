"""配置加载测试（G2：确认 .env 中的 DATABASE_URL 被读取）。"""

from app.config import settings


def test_database_url_loaded_from_env() -> None:
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "doctrain" in settings.database_url

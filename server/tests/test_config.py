"""配置加载测试（G2/C1：确认 .env 中的关键项被读取）。"""

from app.config import settings


def test_database_url_loaded_from_env() -> None:
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "doctrain" in settings.database_url


def test_init_admin_credentials_loaded_from_env() -> None:
    """C1：seed 依赖的管理员账号须来自环境变量，不能是空字符串。"""
    assert settings.init_admin_username.strip()
    assert settings.init_admin_password.strip()


def test_jwt_settings_loaded_from_env() -> None:
    """D-A（D1）：JWT 密钥非空，过期分钟数为正。"""
    assert settings.jwt_secret.strip()
    assert settings.jwt_expire_minutes > 0


def test_cors_origins_parsed() -> None:
    """D-C：CORS_ORIGINS 能解析为至少一个 Origin。"""
    assert len(settings.cors_origin_list) >= 1

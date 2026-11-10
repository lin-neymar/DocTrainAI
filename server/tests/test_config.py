"""配置加载测试（G2/C1：确认 .env 中的关键项被读取）。"""

from app.config import Settings, settings


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


def test_file_upload_settings() -> None:
    """F0：上传目录、大小上限与允许扩展名可读。"""
    assert settings.file_max_mb > 0
    assert settings.file_storage_path.is_absolute()
    assert "pdf" in settings.allowed_extension_list
    assert "md" in settings.allowed_extension_list

def test_log_format_derived_from_app_env_and_overridable() -> None:
    """阶段 4：LOG_FORMAT 缺省随 APP_ENV 推导（production=json，其余=text），可显式覆盖。"""
    assert Settings(app_env="development").effective_log_format == "text"
    assert Settings(app_env="production").effective_log_format == "json"
    assert Settings(app_env="production", log_format="text").effective_log_format == "text"
    assert Settings(app_env="development", log_format="JSON").effective_log_format == "json"
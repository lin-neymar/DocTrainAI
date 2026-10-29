"""全局运行配置（pydantic-settings）。

职责：集中读取环境变量与仓库根目录 .env；禁止在业务代码里硬编码密钥与连接串。
ROOT_DIR 指向 DocTrainAI/ 根目录（与 compose.yaml、.env 同级）。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """运行配置只从环境变量和仓库根目录的 .env 读取。"""

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    app_env: str = "development"  # 开发环境，注解只是提示，不是强制锁类型
    # 与 .env 中 DATABASE_URL 对应；G4 database.py 用此连接 PostgreSQL
    database_url: str

    # C1：scripts/seed.py 创建初始管理员时读取；勿在代码里写死生产密码
    init_admin_username: str
    init_admin_password: str


settings = Settings()

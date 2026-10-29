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

    # D-A（D1）：JWT 签发与校验；JWT_SECRET 必须足够随机，生产环境务必更换
    jwt_secret: str
    # 有效分钟数，默认 480（8 小时）；可被环境变量 JWT_EXPIRE_MINUTES 覆盖
    jwt_expire_minutes: int = 480

    # D-C：允许跨域访问 API 的前端 Origin，英文逗号分隔（Vite 默认 http://localhost:5173）
    cors_origins: str = "http://localhost:5173"

    @property
    # 实现：把 CORS_ORIGINS 拆成 Origin 列表
    def cors_origin_list(self) -> list[str]:
        """解析 CORS_ORIGINS → CORSMiddleware 的 allow_origins 列表。"""
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]


settings = Settings()

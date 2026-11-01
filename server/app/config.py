"""全局运行配置（pydantic-settings）。

职责：集中读取环境变量与仓库根目录 .env；禁止在业务代码里硬编码密钥与连接串。
ROOT_DIR 指向 DocTrainAI/ 根目录（与 compose.yaml、.env 同级）。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 仓库根 DocTrainAI/（.env、compose.yaml 同级）
ROOT_DIR = Path(__file__).resolve().parents[2]
# server/（uvicorn 工作目录；相对路径的 FILE_STORAGE_DIR 以此为基准）
SERVER_DIR = Path(__file__).resolve().parents[1]


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

    # F0：文档原文件存储与上传限制（相对路径相对于 server/）
    file_storage_dir: str = "storage"
    file_max_mb: int = 20
    # 英文逗号分隔，不含点号；默认含办公格式
    allowed_extensions: str = "pdf,md,docx,xlsx,pptx"

    # 存储后端：阶段 1 仅 local；s3 等取值阶段 1 禁止实现客户端
    storage_backend: str = "local"
    # 以下 S3_* 仅预留配置位，阶段 1 不读取实现（extra=ignore 亦可用注释写在 .env.example）
    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str | None = None

    # D3：LibreOffice 预览转换（可执行文件路径可空=自动探测；超时秒）
    libreoffice_path: str | None = None
    libreoffice_timeout_seconds: int = 60

    @property
    # 实现：把 CORS_ORIGINS 拆成 Origin 列表
    def cors_origin_list(self) -> list[str]:
        """解析 CORS_ORIGINS → CORSMiddleware 的 allow_origins 列表。"""
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @property
    # 实现：解析上传允许的扩展名列表（小写、无点）
    def allowed_extension_list(self) -> list[str]:
        return [
            part.strip().lower().lstrip(".")
            for part in self.allowed_extensions.split(",")
            if part.strip()
        ]

    @property
    # 实现：得到原文件存储目录的绝对 Path
    def file_storage_path(self) -> Path:
        path = Path(self.file_storage_dir)
        if path.is_absolute():
            return path
        return (SERVER_DIR / path).resolve()


settings = Settings()

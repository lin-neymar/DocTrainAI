# 阶段 4：server 镜像（api / worker 共用）
# api：uvicorn 跑 FastAPI；worker：arq 跑解析任务（同镜像不同命令，见 compose.yaml）
# 构建上下文 = server/（compose build: context: ./server）
FROM python:3.11-slim

# 办公预览转换依赖：LibreOffice writer/calc/impress（soffice 命令行）
# --no-install-recommends 只装本体，控制镜像体积
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-writer libreoffice-calc libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

# 日志直接输出 stdout/stderr（容器日志采集的标准姿势），不生成 .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 先拷依赖清单再安装：requirements 不变时命中 Docker 层缓存，改代码不必重装
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 再拷应用代码（.dockerignore 已排除 .venv/缓存/本地存储，tests 保留用于构建期门禁）
COPY . .

# 阶段 4 门禁内建：构建即校验（ruff 静态检查 + pytest）
# 构建上下文无 .env：注入 CI 占位值满足 Settings 四个必填字段（database_url/init_admin_*/jwt_secret），
# 真实密钥只在运行期由 compose 注入；conftest 连不上占位库时自动降级，DB 用例 skip
RUN ruff check app tests \
    && DATABASE_URL=postgresql+psycopg://ci:ci@127.0.0.1:5432/ci_doctrain \
       INIT_ADMIN_USERNAME=ci-admin \
       INIT_ADMIN_PASSWORD=ci-placeholder-password \
       JWT_SECRET=ci-placeholder-secret-not-for-production \
       python3 -m pytest -q

# 入口：alembic upgrade head + 幂等 seed 后 exec 传入命令（首参 worker 时跳过迁移）
ENTRYPOINT ["./docker-entrypoint.sh"]
# 默认命令（compose 会显式覆盖）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
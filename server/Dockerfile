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

# 再拷应用代码（.dockerignore 已排除 .venv/缓存/测试/本地存储）
COPY . .

# 入口：alembic upgrade head + 幂等 seed 后 exec 传入命令（首参 worker 时跳过迁移）
ENTRYPOINT ["./docker-entrypoint.sh"]
# 默认命令（compose 会显式覆盖）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
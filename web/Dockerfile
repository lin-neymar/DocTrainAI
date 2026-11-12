# 阶段 4：web 镜像（多阶段：node 构建 → nginx:alpine 托管 dist）
# 构建上下文 = 仓库根目录（Gitee Go build@docker 固定根目录上下文；本地：docker build -f web/Dockerfile .）
# 实验：验证 Gitee Go 构建机直连 Docker Hub（若 i/o timeout 则回退 ACR 基础镜像方案）

# ---------- 构建阶段 ----------
FROM --platform=linux/amd64 node:22-alpine AS builder
WORKDIR /app

# 先拷依赖清单再 npm ci：lockfile 不变时命中 Docker 层缓存
COPY web/package.json web/package-lock.json web/.npmrc ./
RUN npm ci

COPY web/ .
# 阶段 4 门禁内建：lint + 格式校验 + 构建（build 含 vue-tsc typecheck），任一失败即镜像构建失败
RUN npm run lint && npx prettier --check . && npm run build

# ---------- 运行阶段 ----------
FROM --platform=linux/amd64 nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
# 阶段 4：web 镜像（多阶段：node 构建 → nginx:alpine 托管 dist）
# 构建上下文 = 仓库根目录（本地：docker build -f web/Dockerfile .；Jenkins 流水线同样以根目录为上下文）
# 平台固定 amd64：云端构建机与服务器均为 amd64；基础镜像托管在 ACR 的 -amd64 单平台 tag

# ---------- 构建阶段 ----------
FROM --platform=linux/amd64 crpi-8kb0sh7oyiobdzwv.cn-shenzhen.personal.cr.aliyuncs.com/doctrain/node:22-alpine-amd64 AS builder
WORKDIR /app

# 先拷依赖清单再 npm ci：lockfile 不变时命中 Docker 层缓存
COPY web/package.json web/package-lock.json web/.npmrc ./
RUN npm ci

COPY web/ .
# 阶段 4 门禁内建：lint + 格式校验 + 构建（build 含 vue-tsc typecheck），任一失败即镜像构建失败
RUN npm run lint && npx prettier --check . && npm run build

# ---------- 运行阶段 ----------
FROM --platform=linux/amd64 crpi-8kb0sh7oyiobdzwv.cn-shenzhen.personal.cr.aliyuncs.com/doctrain/nginx:alpine-amd64
COPY --from=builder /app/dist /usr/share/nginx/html
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
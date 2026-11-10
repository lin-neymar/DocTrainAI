# 阶段 4：web 镜像（多阶段：node 构建 → nginx:alpine 托管 dist）
# 构建上下文 = web/

# ---------- 构建阶段 ----------
FROM node:22-alpine AS builder
WORKDIR /app

# 先拷依赖清单再 npm ci：lockfile 不变时命中 Docker 层缓存
COPY package.json package-lock.json .npmrc ./
RUN npm ci

COPY . .
# 生产构建：VITE_API_BASE_URL 留空 = 同源 /api（由 nginx 反代）
RUN npm run build

# ---------- 运行阶段 ----------
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
# 阶段 4：web 镜像（多阶段：node 构建 → nginx:alpine 托管 dist）
# 构建上下文 = web/

# ---------- 构建阶段 ----------
FROM node:22-alpine AS builder
WORKDIR /app

# 先拷依赖清单再 npm ci：lockfile 不变时命中 Docker 层缓存
COPY package.json package-lock.json .npmrc ./
RUN npm ci

COPY . .
# 阶段 4 门禁内建：lint + 格式校验 + 构建（build 含 vue-tsc typecheck），任一失败即镜像构建失败
RUN npm run lint && npx prettier --check . && npm run build

# ---------- 运行阶段 ----------
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# 安装前端依赖
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# 复制前端源码
COPY frontend/ .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

FROM node:20-alpine AS builder

WORKDIR /app

# 先复制依赖清单（Docker 缓存）
COPY package.json ./
RUN npm install --registry=https://registry.npmmirror.com

# 复制源码并构建
COPY . .
RUN npm run build


# —— 生产阶段：Nginx 托管静态文件 ——
FROM nginx:alpine

# 自定义 nginx.conf（前端 history 模式路由 + /api 反代到 backend）
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

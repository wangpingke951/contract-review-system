# backend/Dockerfile — Phase 1（基础镜像 + 依赖）
# api-backend 和 celery-worker 共用同一镜像，启动命令在 docker-compose.yml 中指定

FROM python:3.11-slim

# —— 系统依赖 ——
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# —— 工作目录 ——
WORKDIR /app

# —— 先复制依赖清单（利用 Docker 缓存层）———
COPY requirements.txt .

# —— 安装依赖 ——
# 使用清华镜像加速，生产环境可去掉 -i 参数
RUN pip install --no-cache-dir -r requirements.txt

# —— 复制后端代码 ——
COPY app/ ./app/

# —— 创建数据目录 ——
RUN mkdir -p /app/data/uploads

# —— 默认命令（docker-compose.yml 中会覆盖为 uvicorn 或 celery）———
EXPOSE 8000
CMD ["python", "-c", "print('Backend image ready. Use docker-compose up to start api-backend or celery-worker.')"]

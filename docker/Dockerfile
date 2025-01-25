# 构建阶段
FROM --platform=$BUILDPLATFORM python:3.9-alpine AS builder

WORKDIR /app

# 安装构建依赖
RUN apk add --no-cache --virtual .build-deps \
    build-base \
    libffi-dev \
    openssl-dev \
    zlib-dev \
    jpeg-dev \
    musl-dev \
    gcc \
    make \
    pkgconf

# 安装 ffmpeg
RUN apk add --no-cache ffmpeg

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt \
    && find /usr/local -type d -name '__pycache__' -exec rm -rf {} + \
    && find /usr/local -type f -name '*.py[co]' -delete \
    && apk del .build-deps

# 运行阶段
FROM python:3.9-alpine

WORKDIR /app

# 安装运行时依赖
RUN apk add --no-cache ffmpeg \
    && addgroup -S appgroup && adduser -S appuser -G appgroup

# 从构建阶段复制Python包
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY src/ src/
COPY requirements.txt .
COPY .env.example .env

# 创建数据目录并设置权限
RUN mkdir -p /app/Audiobooks \
    && mkdir -p /app/download_tasks \
    && mkdir -p /app/download_history \
    && mkdir -p /app/config \
    && chown -R appuser:appgroup /app \
    && chmod -R 755 /app

# 暴露端口
EXPOSE 5000

# 设置数据卷
VOLUME ["/app/Audiobooks", "/app/download_tasks", "/app/download_history", "/app/config"]

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# 切换到非root用户
USER appuser

# 设置默认命令
CMD ["python", "src/app.py"]

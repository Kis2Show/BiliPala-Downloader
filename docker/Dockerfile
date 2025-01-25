# 构建阶段
FROM --platform=$BUILDPLATFORM python:3.9-alpine AS builder

WORKDIR /app

# 安装构建依赖
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    zlib-dev \
    jpeg-dev \
    ffmpeg \
    musl-dev \
    gcc \
    make \
    pkgconf

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

# 清理构建缓存
RUN find /usr/local -type d -name '__pycache__' -exec rm -rf {} + \
    && find /usr/local -type f -name '*.py[co]' -delete

# 运行阶段
FROM python:3.9-alpine

WORKDIR /app

# 安装运行时依赖
RUN apk add --no-cache ffmpeg

# 从构建阶段复制已安装的Python包
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY src/ src/
COPY requirements.txt .
COPY .env.example .env

# 创建数据目录
RUN mkdir -p /app/Audiobooks

# 暴露端口
EXPOSE 5000

# 设置数据卷
VOLUME /app/Audiobooks
VOLUME /app/config

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 设置默认命令
CMD ["python", "src/app.py"]

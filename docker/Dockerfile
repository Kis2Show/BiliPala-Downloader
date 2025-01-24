# 构建阶段
FROM --platform=$BUILDPLATFORM python:3.9-slim AS builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    zlib1g-dev \
    libjpeg-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

# 运行阶段
FROM python:3.9-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

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

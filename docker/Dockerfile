# 构建阶段
FROM --platform=$BUILDPLATFORM python:3.9-alpine AS builder

WORKDIR /app

RUN apk add --update --no-cache \
  coreutils  # 确保完整sed功能

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
  pkgconf \
  git \
  autoconf \
  automake \
  libtool \
  yasm \
  nasm \
  lame-dev \
  x264-dev  

# 编译参数优化
ENV ASFLAGS="-f elf64"
ENV CFLAGS="-O2 -fno-stack-protector"
ENV CXXFLAGS="${CFLAGS}"

# 克隆并编译 FFmpeg 核心组件
RUN git clone --depth 1 --branch n5.1.3 https://github.com/FFmpeg/FFmpeg.git /tmp/ffmpeg && \
  cd /tmp/ffmpeg && \
  if [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
  sed -i 's/shrl \([^,]*\),%\(e\|r\)cx/shrl \1,%ecx/' libavcodec/x86/mathops.h; \
  sed -i 's/shrl \([^,]*\),%\(e\|r\)ax/shrl \1,%eax/' libavcodec/x86/mathops.h; \
  fi && \
  ./configure \
  --prefix=/opt/ffmpeg \
  --enable-gpl \
  --enable-libx264 \
  --enable-libmp3lame \
  --enable-openssl \
  --enable-nonfree \
  $(if [ "$TARGETPLATFORM" = "linux/amd64" ]; then echo "--disable-asm"; else echo "--enable-neon"; fi) \
  --disable-doc \
  --disable-avdevice \
  --disable-swresample \
  --disable-postproc \
  --disable-avfilter \
  --disable-network \
  --disable-debug \
  --extra-cflags="-I/usr/include" \
  --extra-ldflags="-L/usr/lib" \
  --arch=$(if [ "$TARGETPLATFORM" = "linux/amd64" ]; then echo "x86_64"; else echo "aarch64"; fi) && \
  make -j$(nproc) && \
  make install && \
  rm -rf /tmp/ffmpeg

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt \
  && find /usr/local -type d -name '__pycache__' -exec rm -rf {} + \
  && find /usr/local -type f -name '*.py[co]' -delete \
  && apk del .build-deps

# 运行阶段
FROM alpine:3.18

WORKDIR /app

# 安装运行时依赖
RUN case $TARGETPLATFORM in \
  "linux/amd64") apk add --no-cache libgcc libquadmath ;; \
  "linux/arm64") apk add --no-cache libgomp ;; \
  esac && \
  apk add --no-cache \
  libstdc++ \
  libjpeg \
  libwebp \
  openssl \
  freetype \
  ffmpeg \
  python3

# 从构建阶段复制Python包
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /opt/ffmpeg /opt/ffmpeg

# 添加非root用户
RUN addgroup -S appgroup && \
  adduser -S appuser -G appgroup -h /app && \
  mkdir -p /app/{audiobooks,download_tasks,download_history,config} && \
  chown -R appuser:appgroup /app && \
  chmod -R 755 /app

# 复制应用代码和配置文件
COPY ../src/ src/
COPY ../requirements.txt .
COPY ../.env.example .env

# 设置环境变量
ENV PATH="/usr/local/bin:/opt/ffmpeg/bin:/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/app

# 暴露端口
EXPOSE 5000

# 设置数据卷
VOLUME ["/app/audiobooks", "/app/download_tasks", "/app/download_history", "/app/config"]

# 切换到非root用户
USER appuser

# 设置默认命令
CMD ["python", "src/app.py"]
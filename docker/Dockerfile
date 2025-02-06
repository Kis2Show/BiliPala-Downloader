# ===== 构建阶段 =====
FROM --platform=$BUILDPLATFORM python:3.9-alpine AS builder

# 声明必要的构建参数
ARG TARGETPLATFORM

WORKDIR /app

# 安装系统级依赖
RUN apk update && apk add --no-cache \
  coreutils \
  ca-certificates && \
  update-ca-certificates

# 安装编译工具链
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
  perl \
  lame-dev \
  x264-dev \
  freetype-dev \
  libwebp-dev

# 安装gas-preprocessor（解决GNU assembler问题）
RUN git clone https://github.com/FFmpeg/gas-preprocessor.git /tmp/gas-preprocessor && \
  install -m 755 /tmp/gas-preprocessor/gas-preprocessor.pl /usr/local/bin/ && \
  rm -rf /tmp/gas-preprocessor

# 编译优化参数
ENV CFLAGS="-O3 -fno-stack-protector"
ENV CXXFLAGS="${CFLAGS}"
ENV PKG_CONFIG_PATH="/usr/local/lib/pkgconfig"

# ===== FFmpeg编译段 =====
RUN git clone --depth 1 --branch n5.1.3 https://github.com/FFmpeg/FFmpeg.git /tmp/ffmpeg && \
  cd /tmp/ffmpeg && \

  # 修改x86汇编代码
  ([ "$TARGETPLATFORM" = "linux/amd64" ] && \
  sed -i -e 's/shrl $[^,]*$,%$e\|r$cx/shrl \1,%ecx/g' \
  -e 's/shrl $[^,]*$,%$e\|r$ax/shrl \1,%eax/g' \
  libavcodec/x86/mathops.h || true) && \

  # 配置编译参数
  ./configure \
  --prefix=/opt/ffmpeg \
  --enable-gpl \
  --enable-libx264 \
  --enable-libmp3lame \
  --enable-openssl \
  --enable-nonfree \
  $(if [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
  echo "--disable-asm --arch=x86_64"; \
  else \
  echo "--enable-neon --arch=aarch64"; \
  fi) \
  --disable-doc \
  --disable-avdevice \
  --disable-swresample \
  --disable-postproc \
  --disable-avfilter \
  --disable-network \
  --disable-debug \
  --extra-cflags="-I/usr/include -fPIC" \
  --extra-ldflags="-L/usr/lib -Wl,-rpath,/opt/ffmpeg/lib" && \

  # 编译安装
  make -j$(nproc) && \
  make install && \
  rm -rf /tmp/ffmpeg

# ===== Python依赖安装 =====
COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt && \
  find /usr/local -depth \
  \( \
  $ -type d -name __pycache__ $ \
  -o \
  $ -type f -name '*.py[co]' $ \
  \) -exec rm -rf {} + && \
  apk del .build-deps

# ===== 运行阶段 =====
FROM alpine:3.18

WORKDIR /app

# 安装运行时依赖
RUN apk add --no-cache \
  libgcc \
  libstdc++ \
  libjpeg \
  libwebp \
  openssl \
  freetype \
  lame \
  x264 \
  libass \
  zlib \
  ffmpeg \
  python3 && \
  # 配置动态库路径
  echo "/opt/ffmpeg/lib" >> /etc/ld.so.conf.d/ffmpeg.conf && \
  ldconfig

# 从构建阶段复制必要文件
COPY --from=builder /opt/ffmpeg /opt/ffmpeg
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 添加应用用户
RUN addgroup -S appgroup && \
  adduser -S appuser -G appgroup -h /app && \
  mkdir -p /app/{audiobooks,download_tasks,download_history,config} && \
  chown -R appuser:appgroup /app && \
  chmod -R 755 /app

# 复制应用代码
COPY src/ src/
COPY requirements.txt .
COPY .env.example .env

# 设置环境变量
ENV PATH="/usr/local/bin:/opt/ffmpeg/bin:$PATH"
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
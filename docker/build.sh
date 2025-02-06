#!/bin/bash

# 初始化buildx
docker buildx create --use

# 构建并推送多架构镜像
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t nbzzd6/bilipala-downloader:latest \
  --push .

echo "Multi-arch image built and pushed successfully"
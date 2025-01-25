# Bilibili 音频下载器

## 环境配置

### 1. 环境变量配置
复制`.env.example`文件并重命名为`.env`，然后根据需要进行配置：

```bash
cp .env.example .env
```

主要配置项：
- `BILIBILI_COOKIE`: Bilibili登录cookie（可选）
- `OUTPUT_DIR`: 音频文件输出目录（默认：Audiobooks/）
- `QUALITY`: 音频质量（默认：192k）
- `FFMPEG_PATH`: FFmpeg路径（默认：系统PATH）

## Docker 使用

### 1. 构建Docker镜像
```bash
docker build -t bilibili-audio-downloader -f docker/Dockerfile .
```

### 2. 运行容器
```bash
docker run -it --rm \
  -v $(pwd)/Audiobooks:/app/Audiobooks \
  -v $(pwd)/.env:/app/.env \
  bilibili-audio-downloader \
  python src/app.py -u [视频URL]
```

### 3. 使用docker-compose
```bash
docker-compose -f docker/docker-compose.yml up
```

## 注意事项
1. 确保Docker已安装并运行
2. 首次运行可能需要较长时间构建镜像
3. 建议分配至少2GB内存给Docker
4. 输出目录会自动创建
# B站音频下载工具

![Python版本](https://img.shields.io/badge/Python-3.8%2B-blue)
![Docker支持](https://img.shields.io/badge/Docker-✓-success)

本工具用于下载B站视频的纯净音频内容，支持多种音质选择和自动元数据 tagging。

## 主要特性

- 🎵 一键下载B站视频的音频轨道
- 📁 自动整理到分类目录
- 🔍 智能元数据提取（标题/UP主/封面等）
- 🐳 Docker容器化部署
- � 下载历史记录追踪

## 快速开始

### 前置要求
- Python 3.8+
- FFmpeg 5.0+ ([下载链接](https://ffmpeg.org/))
- Chrome浏览器 + chromedriver

### 安装步骤
```bash
git clone https://github.com/Kis2Show/bilibili_audio_downloader.git
cd bilibili_audio_downloader
pip install -r requirements.txt
```

### 基础使用
```python
from downloader import BilibiliAudioDownloader

downloader = BilibiliAudioDownloader(
    output_dir="audiobooks",
    quality='flac'  # 可选: flac/mp3_320k/mp3_128k
)

# 下载单个视频
downloader.download("https://www.bilibili.com/video/BV1xx411c7XX")

# 批量下载
with open("url_list.txt") as f:
    for url in f.readlines():
        downloader.download(url.strip())
```

## 🐳 Docker部署
```bash
# 构建镜像
docker build -t bilibili-audio .

# 运行容器（将/path/to/config映射到容器内）
docker run -it --rm \
  -v /path/to/config:/app/config \  # 用于存放.env配置文件
  -v /path/to/downloads:/app/audiobooks \
  bilibili-audio
```

## 配置选项
在`.env`文件中配置：
```ini
# 代理设置（可选）
PROXY_SERVER=127.0.0.1:7890

# 下载并发数
MAX_WORKERS=3

# 默认下载目录
OUTPUT_ROOT=audiobooks
```

## 注意事项
1. 首次使用需安装chromedriver：
```bash
# macOS/Linux
brew install chromedriver

# Windows
choco install chromedriver
```

2. FFmpeg路径配置：
```python
# 在代码中指定自定义路径
downloader.set_ffmpeg_path("/path/to/ffmpeg")
```

## 测试验证
```bash
pytest tests/ -v
```

## 贡献指南
欢迎提交PR！请确保：
1. 所有修改包含单元测试
2. 通过flake8代码规范检查
3. 更新相关文档

## 许可证
MIT License © 2024 Kis2Show

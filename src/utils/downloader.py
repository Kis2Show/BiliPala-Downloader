import yt_dlp
import os
import re
import requests
from typing import Generator, Dict, Any, List
from PIL import Image, ImageFilter, ImageOps
from io import BytesIO
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
import logging
from datetime import datetime
import time
import json
import hashlib
import threading

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('BiliDownloader')

class BiliDownloader:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com',
            'Origin': 'https://www.bilibili.com',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        self.base_url = "https://www.bilibili.com/video/"
        self.history_dir = "download_history"
        self.task_dir = "download_tasks"
        os.makedirs(self.history_dir, exist_ok=True)
        os.makedirs(self.task_dir, exist_ok=True)
        self.history_file = os.path.join(self.history_dir, "history.json")
        self.download_history = self.load_download_history()
        self.cover_queue = []  # 封面处理队列
        self.active_tasks = {}  # 当前活动任务
        logger.info("BiliDownloader 初始化完成")

    def load_download_history(self) -> dict:
        """加载下载历史记录"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                logger.info(f"加载下载历史记录：{len(history)} 条记录")
                return history
        except Exception as e:
            logger.error(f"加载下载历史记录失败：{str(e)}")
        return {}

    def save_download_history(self):
        """保存下载历史记录"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.download_history, f, ensure_ascii=False, indent=2)
            logger.info("下载历史记录已保存")
        except Exception as e:
            logger.error(f"保存下载历史记录失败：{str(e)}")

    def get_video_key(self, bvid: str, p: int, title: str) -> str:
        """生成视频唯一标识"""
        key_str = f"{bvid}_p{p}_{title}"
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()

    def is_downloaded(self, bvid: str, p: int, info: dict) -> tuple[bool, str, bool]:
        """检查视频是否已下载
        返回：(是否已下载，已下载文件路径，是否支持续传)
        """
        title = info.get('title', '')
        video_key = self.get_video_key(bvid, p, title)

        if video_key in self.download_history:
            history_info = self.download_history[video_key]
            mp3_path = history_info.get('file_path')

            # 检查文件是否存在
            if mp3_path and os.path.exists(mp3_path):
                # 检查文件是否完整
                expected_size = history_info.get('file_size', 0)
                actual_size = os.path.getsize(mp3_path)

                if actual_size >= expected_size:
                    logger.info(f"找到完整的历史下载记录：{mp3_path}")
                    return True, mp3_path, False
                else:
                    logger.info(f"找到不完整的历史下载记录：{mp3_path} ({actual_size}/{expected_size} bytes)")
                    return False, mp3_path, True
            else:
                # 如果文件不存在，删除历史记录
                logger.info(f"历史文件不存在，清除记录：{mp3_path}")
                del self.download_history[video_key]
                self.save_download_history()

        return False, "", False

    def add_download_history(self, bvid: str, p: int, file_path: str, info: dict):
        """添加下载历史记录"""
        title = info.get('title', '')
        video_key = self.get_video_key(bvid, p, title)

        self.download_history[video_key] = {
            'bvid': bvid,
            'p': p,
            'title': title,
            'file_path': file_path,
            'download_time': datetime.now().isoformat(),
            'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', ''),
            'upload_date': info.get('upload_date', '')
        }
        self.save_download_history()
        logger.info(f"添加下载记录：{title}")

    def extract_bvid(self, url: str) -> str:
        """从 URL 中提取 BV 号"""
        pattern = r"BV[a-zA-Z0-9]+"
        match = re.search(pattern, url)
        if not match:
            logger.error(f"无效的哔哩哔哩链接：{url}")
            raise ValueError("无效的哔哩哔哩链接")
        bvid = match.group()
        logger.info(f"成功提取 BV 号：{bvid}")
        return bvid

    def get_cover_image(self, info):
        try:
            # 尝试获取封面URL
            cover_url = info.get('thumbnail')
            if cover_url:
                logger.info(f"找到封面 URL: {cover_url}")
                response = requests.get(cover_url, headers=self.headers)
                if response.status_code == 200:
                    logger.info("封面下载成功，开始处理图片")
                    # 打开图片
                    img = Image.open(BytesIO(response.content))
                    original_size = img.size
                    logger.info(f"原始图片尺寸：{original_size}")

                    # 以长边为基准创建正方形画布
                    max_side = max(img.width, img.height)
                    # 创建新的正方形画布
                    square_img = Image.new('RGB', (max_side, max_side), (255, 255, 255))

                    # 计算粘贴位置
                    x_offset = (max_side - img.width) // 2
                    y_offset = (max_side - img.height) // 2

                    # 将原图粘贴到正方形画布中心
                    square_img.paste(img, (x_offset, y_offset))

                    # 使用智能填充处理边缘
                    if img.width < max_side:
                        # 左右边缘需要填充
                        left_edge = img.crop((0, 0, 1, img.height))
                        right_edge = img.crop((img.width-1, 0, img.width, img.height))
                        for x in range(0, x_offset):
                            square_img.paste(left_edge, (x, y_offset))
                        for x in range(x_offset + img.width, max_side):
                            square_img.paste(right_edge, (x, y_offset))

                    if img.height < max_side:
                        # 上下边缘需要填充
                        top_edge = img.crop((0, 0, img.width, 1))
                        bottom_edge = img.crop((0, img.height-1, img.width, img.height))
                        for y in range(0, y_offset):
                            square_img.paste(top_edge, (x_offset, y))
                        for y in range(y_offset + img.height, max_side):
                            square_img.paste(bottom_edge, (x_offset, y))

                    # 创建仅包含填充区域的蒙版
                    mask = Image.new('L', square_img.size, 0)
                    # 绘制原始图片区域（不模糊）
                    mask.paste(255, (x_offset, y_offset, x_offset + img.width, y_offset + img.height))
                    # 反转蒙版以获取填充区域
                    mask = ImageOps.invert(mask)

                    # 仅对填充区域应用模糊
                    blurred = square_img.filter(ImageFilter.GaussianBlur(radius=10))
                    # 将模糊后的填充区域与原始图片合并
                    square_img.paste(blurred, mask=mask)
                    logger.info(f"正方形画布尺寸：{square_img.size} (已应用边缘模糊)")

                    # 调整大小为 400x400
                    img = square_img.resize((400, 400), Image.Resampling.LANCZOS)

                    # 转换为字节
                    output = BytesIO()
                    img.save(output, format='JPEG', quality=95)
                    logger.info(f"封面处理完成：{original_size} -> (400x400)")
                    return output.getvalue()
            else:
                logger.warning("未找到封面URL")
                return None
        except Exception as e:
            logger.error(f"获取封面图片失败: {str(e)}")
            return None

    def embed_cover(self, mp3_path: str, cover_data: bytes):
        """将封面嵌入到 MP3 文件中"""
        if not cover_data:
            logger.warning(f"没有封面数据，跳过封面嵌入：{os.path.basename(mp3_path)}")
            return

        try:
            logger.info(f"开始为音频文件添加封面：{os.path.basename(mp3_path)}")

            # 等待文件可用，最多等待10秒
            for _ in range(10):
                if os.path.exists(mp3_path):
                    # 检查文件是否完整（不是正在写入状态）
                    try:
                        with open(mp3_path, 'rb') as f:
                            f.seek(-128, 2)  # 尝试读取文件末尾
                        break
                    except:
                        pass
                time.sleep(1)
            else:
                raise FileNotFoundError(f"等待MP3文件超时：{mp3_path}")

            audio = MP3(mp3_path, ID3=ID3)

            # 如果没有 ID3 标签，创建一个
            if audio.tags is None:
                audio.add_tags()
                logger.info("创建新的 ID3 标签")

            # 添加封面
            audio.tags.add(
                APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,  # 封面图片
                    desc='Cover',
                    data=cover_data
                )
            )

            # 保存更改
            audio.save(v2_version=3)
            logger.info("封面添加成功")

        except Exception as e:
            logger.error(f"添加封面失败：{str(e)}")

    def get_collection_info(self, mid: str, season_id: str) -> list:
        """获取合集信息"""
        base_url = f"https://api.bilibili.com/x/polymer/web-space/seasons_archives_list"
        collection_data = []
        page_num = 1
        page_size = 30  # 保持与API默认分页大小一致

        try:
            while True:
                params = {
                    'mid': mid,
                    'season_id': season_id,
                    'sort_reverse': 'false',
                    'page_size': page_size,
                    'page_num': page_num
                }
                logger.info(f"请求合集信息：{base_url} 参数：{params}")

                response = requests.get(base_url, headers=self.headers, params=params)
                if response.status_code != 200:
                    logger.error(f"请求失败：HTTP {response.status_code}")
                    raise ValueError("无法获取合集信息")
                
                data = response.json()
                if data['code'] != 0:
                    logger.error(f"API 返回错误：{data['message']}")
                    raise ValueError(data['message'])
                
                # 解析分页信息
                page_info = data.get('data', {}).get('page', {})
                total = page_info.get('total', 0)
                current_page = page_info.get('page_num', 1)

                # 提取当前页视频信息
                for item in data.get('data', {}).get('archives', []):
                    collection_data.append({
                        'bvid': item.get('bvid'),
                        'title': item.get('title'),
                        'cover': item.get('pic')
                    })

                logger.debug(f"当前页 {current_page} 获取到 {len(data['data']['archives'])} 个视频")

                # 判断是否还有下一页
                if page_num * page_size >= total:
                    logger.info(f"分页获取完成，总视频数：{total} 实际获取：{len(collection_data)}")

                    break

                # 移动到下一页
                page_num += 1

            logger.info(f"成功获取合集信息：共 {len(collection_data)} 个视频")
            return collection_data
        
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求异常: {str(e)}")
            raise
        except json.JSONDecodeError:
            logger.error("响应内容解析失败")
            raise
        except Exception as e:
            logger.error(f"获取合集信息失败: {str(e)}")
            raise

    def check_playlist(self, params: List[str]) -> dict:
        """检查播放列表或合集信息"""
        if len(params) == 2:
            # 处理合集信息
            mid, season_id = params
            logger.info(f"开始检查合集：mid={mid}, season_id={season_id}")
            try:
                collection_data = self.get_collection_info(mid, season_id)
                logger.info(f"成功获取合集信息：共 {len(collection_data)} 个视频")
                return {
                    'type': 'collection',
                    'mid': mid,
                    'season_id': season_id,
                    'count': len(collection_data)
                }
            except Exception as e:
                logger.error(f"检查合集失败：{str(e)}")
                raise
        elif len(params) == 1:
            # 处理单个视频或合集 URL
            bvid_or_url = params[0]
            # 判断是否为合集URL
            collection_match = re.match(r'https://www\.bilibili\.com/medialist/play/(\d+)\?from=.*&season_id=(\d+)', bvid_or_url)
            if collection_match:
                mid = collection_match.group(1)
                season_id = collection_match.group(2)
                logger.info(f"检测到合集：mid={mid}, season_id={season_id}")
                collection_data = self.get_collection_info(mid, season_id)
                return {
                    'type': 'collection',
                    'mid': mid,
                    'season_id': season_id,
                    'count': len(collection_data)
                }
            else:
                # 处理普通 BV 号或单个视频 URL
                url = f"{self.base_url}{bvid_or_url}"
                logger.info(f"开始检查播放列表：{url}")

                try:
                    # 使用 requests 获取页面内容
                    response = requests.get(url, headers=self.headers)
                    if response.status_code != 200:
                        logger.error(f"请求失败：HTTP {response.status_code}")
                        return {'type': 'video', 'count': 1}

                    # 在页面内容中查找分 P 信息
                    content = response.text
                    # 查找包含分 P 数量的模式
                    pattern = r'"page":(\d+),'
                    matches = re.findall(pattern, content)

                    if matches:
                        # 如果找到匹配，取最大的数字
                        max_page = max(map(int, matches))
                        logger.info(f"检测到多 P 视频，共 {max_page} 个分 P")
                        return {'type': 'video', 'count': max_page}
                    else:
                        logger.info("未检测到分 P 信息，视频为单集")
                        return {'type': 'video', 'count': 1}

                except Exception as e:
                    logger.error(f"检查播放列表时出错：{str(e)}")
                    return {'type': 'video', 'count': 1}
        else:
            raise ValueError("参数数量不正确，应为1个或2个参数")

    def save_task_state(self, task_id: str, state: dict):
        """保存任务状态"""
        task_file = os.path.join(self.task_dir, f"{task_id}.json")
        try:
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info(f"任务状态已保存：{task_id}")
        except Exception as e:
            logger.error(f"保存任务状态失败：{str(e)}")

    def load_task_state(self, task_id: str) -> dict:
        """加载任务状态"""
        task_file = os.path.join(self.task_dir, f"{task_id}.json")
        try:
            if os.path.exists(task_file):
                with open(task_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                logger.info(f"加载任务状态：{task_id}")
                return state
        except Exception as e:
            logger.error(f"加载任务状态失败：{str(e)}")
        return {}

    def cleanup_task_state(self, task_id: str):
        """清理已完成任务状态"""
        task_file = os.path.join(self.task_dir, f"{task_id}.json")
        try:
            if os.path.exists(task_file):
                os.remove(task_file)
                logger.info(f"清理任务状态文件：{task_id}")
        except Exception as e:
            logger.error(f"清理任务状态文件失败：{str(e)}")

    def wait_for_file(self, filepath: str, timeout: int = 30) -> bool:
        """等待文件出现并可访问"""
        logger.info(f"等待文件：{os.path.basename(filepath)}")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if os.path.exists(filepath):
                try:
                    # 尝试打开文件
                    with open(filepath, 'rb') as f:
                        f.read(1)
                    logger.info(f"文件已就绪：{os.path.basename(filepath)}")
                    return True
                except:
                    pass
            time.sleep(1)
        logger.error(f"等待文件超时：{os.path.basename(filepath)}")
        return False

    def download(self, bvid: str, output_dir: str, rename: bool = False) -> Generator[Dict[str, Any], None, None]:
        """下载音频文件"""
        start_time = datetime.now()
        base_path = os.path.join(os.getenv('DOWNLOAD_DIR', 'audiobooks'), output_dir)
        os.makedirs(base_path, exist_ok=True)
        logger.info(f"创建输出目录：{base_path}")

        # 生成任务ID
        task_id = hashlib.md5(f"{bvid}_{output_dir}".encode('utf-8')).hexdigest()
        self.active_tasks[task_id] = {
            'bvid': bvid,
            'output_dir': output_dir,
            'start_time': start_time.isoformat(),
            'status': 'running',
            'progress': 0
        }
        self.save_task_state(task_id, self.active_tasks[task_id])

        # 加载下载配置
        max_retries = int(os.getenv('MAX_RETRIES', '3'))
        timeout = int(os.getenv('TIMEOUT', '30'))
        concurrent_downloads = int(os.getenv('CONCURRENT_DOWNLOADS', '5'))

        # 创建一个队列来存储进度信息
        progress_queue = []

        # 进度回调函数
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    # 尝试从 _percent_str 获取进度
                    if '_percent_str' in d:
                        percent = float(d['_percent_str'].strip('%'))
                    # 如果没有 _percent_str，尝试从已下载字节和总字节计算
                    elif 'downloaded_bytes' in d and 'total_bytes' in d:
                        percent = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    # 如果都没有，使用预估总字节
                    elif 'downloaded_bytes' in d and 'total_bytes_estimate' in d:
                        percent = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                    else:
                        percent = 0

                    progress_queue.append({
                        'status': 'progress',
                        'progress': percent,
                        'speed': d.get('_speed_str', 'N/A'),
                        'eta': d.get('_eta_str', 'N/A'),
                        'title': d.get('info_dict', {}).get('title', '')
                    })
                except (ValueError, ZeroDivisionError):
                    pass
            elif d['status'] == 'finished':
                progress_queue.append({
                    'status': 'progress',
                    'progress': 100,
                    'speed': 'N/A',
                    'eta': '0s',
                    'title': d.get('info_dict', {}).get('title', '')
                })

        # 配置下载选项
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(base_path, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': os.getenv('AUDIO_QUALITY', '192k'),
            }],
            'writethumbnail': False,  # 先不下载封面
            'ignoreerrors': True,
            'quiet': False,
            'no_warnings': False,
            'continuedl': True,  # 支持断点续传
            'noprogress': False,
            'progress_hooks': [progress_hook],
            'retries': max_retries,
            'socket_timeout': timeout,
            'concurrent_fragment_downloads': concurrent_downloads,
        }

        count = self.check_playlist([bvid])['count']
        logger.info(f"准备下载 {count} 个视频")

        # 在下载过程中定期检查进度队列
        def check_progress():
            while progress_queue:
                yield progress_queue.pop(0)

        # 在下载过程中定期更新进度
        def update_progress():
            for progress_info in check_progress():
                if progress_info:
                    yield progress_info

        # 封面处理函数
        def process_covers():
            while self.cover_queue:
                mp3_path, cover_data = self.cover_queue.pop(0)
                try:
                    self.embed_cover(mp3_path, cover_data)
                    logger.info(f"成功处理封面：{os.path.basename(mp3_path)}")
                except Exception as e:
                    logger.error(f"处理封面失败：{os.path.basename(mp3_path)} - {str(e)}")

        success_count = 0
        skip_count = 0
        error_count = 0

        for p in range(1, count + 1):
            url = f"{self.base_url}{bvid}?p={p}"
            logger.info(f"处理第 {p}/{count} 个视频：{url}")

            try:
                # 首先获取视频信息
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', '')

                # 检查是否已下载，支持断点续传
                is_downloaded, existing_file, can_resume = self.is_downloaded(bvid, p, info)
                if is_downloaded:
                    logger.info(f"跳过已下载的文件：{existing_file}")
                    skip_count += 1
                    yield {
                        'status': 'skip',
                        'message': f'已跳过重复文件：{os.path.basename(existing_file)}',
                        'progress': (p / count) * 100,  # 基于总视频数计算进度
                        'title': title
                    }
                    continue
                elif can_resume:
                    logger.info(f"发现不完整文件，尝试断点续传：{existing_file}")
                    ydl_opts['outtmpl'] = existing_file

                # 下载新文件
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info("开始下载音频")

                    # 创建下载线程
                    download_thread = threading.Thread(
                        target=ydl.download,
                        args=([url],)
                    )
                    download_thread.start()

                    # 在主线程中检查进度
                    while download_thread.is_alive():
                        # 检查进度队列
                        while progress_queue:
                            progress_info = progress_queue.pop(0)
                            # 修改进度计算逻辑，将单个文件的进度转换为总进度
                            if progress_info['status'] == 'progress':
                                file_progress = progress_info['progress']
                                total_progress = ((p - 1) * 100 + file_progress) / count
                                progress_info['progress'] = total_progress
                            yield progress_info
                        time.sleep(0.1)  # 避免过于频繁的检查

                    # 确保获取最后的进度信息
                    while progress_queue:
                        progress_info = progress_queue.pop(0)
                        # 修改最后的进度信息
                        if progress_info['status'] == 'progress':
                            file_progress = progress_info['progress']
                            total_progress = ((p - 1) * 100 + file_progress) / count
                            progress_info['progress'] = total_progress
                        yield progress_info

                    download_thread.join()
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', '')

                # 获取原始文件名（不带扩展名）
                basename = os.path.splitext(ydl.prepare_filename(info))[0]
                logger.info(f"基础文件名：{os.path.basename(basename)}")

                # 等待 MP3 文件出现
                mp3_filename = f"{basename}.mp3"
                if not self.wait_for_file(mp3_filename):
                    raise FileNotFoundError("MP3 文件生成失败")

                logger.info(f"音频下载完成：{os.path.basename(mp3_filename)}")

                # 获取封面并加入处理队列
                cover_data = self.get_cover_image(info)
                if cover_data:
                    self.cover_queue.append((mp3_filename, cover_data))
                    logger.info(f"封面已加入处理队列：{os.path.basename(mp3_filename)}")
                else:
                    logger.warning("无法获取封面图片")

                # 如果所有音频下载完成，开始处理封面
                if p == count:
                    logger.info("所有音频下载完成，开始处理封面")
                    process_covers()

                final_filename = mp3_filename
                if rename:
                    new_filename = os.path.join(base_path, f"{output_dir}-{p}.mp3")
                    if os.path.exists(mp3_filename):
                        logger.info(f"重命名文件：{os.path.basename(mp3_filename)} -> {os.path.basename(new_filename)}")
                        os.rename(mp3_filename, new_filename)
                        final_filename = new_filename

                # 添加到下载历史
                self.add_download_history(bvid, p, final_filename, info)

                # 清理临时文件
                try:
                    # 清理 JSON 文件
                    info_json = f"{basename}.info.json"
                    if os.path.exists(info_json):
                        os.remove(info_json)
                        logger.info("清理临时 JSON 文件")

                    # 清理其他可能的临时文件
                    for ext in ['.m4a', '.webm', '.part', '.ytdl']:
                        temp_file = f"{basename}{ext}"
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                            logger.info(f"清理临时文件：{os.path.basename(temp_file)}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败：{str(e)}")

                success_count += 1
                yield {
                    'status': 'success',
                    'message': f'已下载：{os.path.basename(final_filename)}',
                    'progress': (p / count) * 100,
                    'title': title
                }
            except Exception as e:
                logger.error(f"下载失败：{str(e)}")
                error_count += 1
                # 清理失败下载的临时文件
                try:
                    if 'basename' in locals():
                        for ext in ['.mp3', '.m4a', '.webm', '.part', '.ytdl', '.info.json']:
                            temp_file = f"{basename}{ext}"
                            if os.path.exists(temp_file):
                                os.remove(temp_file)
                                logger.info(f"清理失败下载的临时文件：{os.path.basename(temp_file)}")
                except Exception as cleanup_error:
                    logger.error(f"清理临时文件失败：{str(cleanup_error)}")

                yield {
                    'status': 'error',
                    'message': f'下载失败：{str(e)}',
                    'progress': (p / count) * 100,
                    'retries_left': 5 - error_count,
                    'title': title
                }

                # 如果重试次数未用完，等待后重试
                if error_count < 5:
                    time.sleep(5 * error_count)  # 重试间隔时间逐渐增加
                    continue
                else:
                    logger.error(f"视频 {p} 下载失败，已达到最大重试次数")
                    # 更新任务状态
                    self.active_tasks[task_id]['status'] = 'failed'
                    self.active_tasks[task_id]['end_time'] = datetime.now().isoformat()
                    self.active_tasks[task_id]['error'] = str(e)
                    self.save_task_state(task_id, self.active_tasks[task_id])
                    self.cleanup_task_state(task_id)
                    break

        end_time = datetime.now()
        duration = end_time - start_time
        logger.info("下载任务完成")
        logger.info(f"总计：{count} 个视频")
        logger.info(f"成功：{success_count} 个")
        logger.info(f"跳过：{skip_count} 个")
        logger.info(f"失败：{error_count} 个")
        logger.info(f"总耗时：{duration.total_seconds():.1f} 秒")

        # 更新任务状态
        self.active_tasks[task_id]['status'] = 'completed'
        self.active_tasks[task_id]['end_time'] = end_time.isoformat()
        self.active_tasks[task_id]['duration'] = duration.total_seconds()
        self.save_task_state(task_id, self.active_tasks[task_id])
        self.cleanup_task_state(task_id)

    def process_cover(self, cover_data):
        try:
            # 打开图片
            img = Image.open(BytesIO(cover_data))
            original_size = img.size
            logger.info(f"原始图片尺寸：{original_size}")

            # 以长边为基准创建正方形画布
            max_side = max(img.width, img.height)
            # 创建新的正方形画布
            square_img = Image.new('RGB', (max_side, max_side), (255, 255, 255))

            # 计算粘贴位置
            x_offset = (max_side - img.width) // 2
            y_offset = (max_side - img.height) // 2

            # 将原图粘贴到正方形画布中心
            square_img.paste(img, (x_offset, y_offset))

            # 使用智能填充处理边缘
            if img.width < max_side:
                # 左右边缘需要填充
                left_edge = img.crop((0, 0, 1, img.height))
                right_edge = img.crop((img.width-1, 0, img.width, img.height))
                for x in range(0, x_offset):
                    square_img.paste(left_edge, (x, y_offset))
                for x in range(x_offset + img.width, max_side):
                    square_img.paste(right_edge, (x, y_offset))

            if img.height < max_side:
                # 上下边缘需要填充
                top_edge = img.crop((0, 0, img.width, 1))
                bottom_edge = img.crop((0, img.height-1, img.width, img.height))
                for y in range(0, y_offset):
                    square_img.paste(top_edge, (x_offset, y))
                for y in range(y_offset + img.height, max_side):
                    square_img.paste(bottom_edge, (x_offset, y))

            # 创建仅包含填充区域的蒙版
            mask = Image.new('L', square_img.size, 0)
            # 绘制原始图片区域（不模糊）
            mask.paste(255, (x_offset, y_offset, x_offset + img.width, y_offset + img.height))
            # 反转蒙版以获取填充区域
            mask = ImageOps.invert(mask)

            # 仅对填充区域应用模糊
            blurred = square_img.filter(ImageFilter.GaussianBlur(radius=10))
            # 将模糊后的填充区域与原始图片合并
            square_img.paste(blurred, mask=mask)
            logger.info(f"正方形画布尺寸：{square_img.size} (已应用边缘模糊)")

            # 调整大小为 400x400
            img = square_img.resize((400, 400), Image.Resampling.LANCZOS)

            # 转换为字节
            output = BytesIO()
            img.save(output, format='JPEG', quality=95)
            logger.info(f"封面处理完成：{original_size} -> (400x400)")
            return output.getvalue()
        except Exception as e:
            logger.error(f"处理封面时出错: {str(e)}")
            return None
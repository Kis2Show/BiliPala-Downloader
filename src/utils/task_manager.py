import os
import json
import threading
from datetime import datetime
from typing import Dict, Optional
import logging
from .downloader import BiliDownloader
from .title_filter import TitleFilter
import yt_dlp

logger = logging.getLogger('TaskManager')

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, dict] = {}
        self.tasks_lock = threading.Lock()
        self.downloader = BiliDownloader()
        self.title_filter = TitleFilter()
        self.tasks_file = "download_tasks/active_tasks.json"
        self.load_tasks()
        
    def load_tasks(self):
        """加载保存的任务状态"""
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    saved_tasks = json.load(f)
                    with self.tasks_lock:
                        self.tasks = saved_tasks
                logger.info(f"已加载 {len(self.tasks)} 个保存的任务")
        except Exception as e:
            logger.error(f"加载任务状态失败: {str(e)}")
            self.tasks = {}

    def save_tasks(self):
        """保存当前任务状态"""
        try:
            os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(self.tasks, f, ensure_ascii=False, indent=2)
            logger.info("任务状态已保存")
        except Exception as e:
            logger.error(f"保存任务状态失败: {str(e)}")

    def create_collection_task(self, mid: str, season_id: str, output_dir: str, rename: bool = False) -> str:
        """创建新的合集下载任务"""
        task_id = f"collection_{mid}_{season_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 获取合集信息
        try:
            collection_data = self.downloader.get_collection_info(mid, season_id)
            titles = [item['title'] for item in collection_data]
        except Exception as e:
            logger.error(f"获取合集信息失败: {str(e)}")
            titles = []

        task = {
            'task_id': task_id,
            'mid': mid,
            'season_id': season_id,
            'titles': titles,
            'output_dir': output_dir,
            'rename': rename,
            'status': 'pending',
            'progress': 0,
            'created_at': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat()
        }
        
        with self.tasks_lock:
            self.tasks[task_id] = task
            self.save_tasks()
        
        # 在新线程中启动下载
        thread = threading.Thread(target=self._download_collection_task, args=(task_id,))
        thread.daemon = True  # 设置为守护线程，这样主程序退出时线程会自动结束
        thread.start()
        
        return task_id

    def _download_collection_task(self, task_id: str):
        """执行合集下载任务"""
        try:
            with self.tasks_lock:
                task = self.tasks[task_id]
                task['status'] = 'running'
                self.save_tasks()

            # 开始下载合集中的每个视频
            collection_data = self.downloader.get_collection_info(task['mid'], task['season_id'])
            total_videos = len(collection_data)
            for index, video in enumerate(collection_data):
                bvid = video['bvid']
                title = video['title']
                
                # 更新任务进度
                progress = (index / total_videos) * 100
                with self.tasks_lock:
                    task = self.tasks[task_id]
                    task['progress'] = progress
                    task['last_update'] = datetime.now().isoformat()
                    self.save_tasks()
                
                # 下载单个视频
                for download_progress in self.downloader.download(bvid, task['output_dir'], task['rename']):
                    if isinstance(download_progress, dict):
                        with self.tasks_lock:
                            task = self.tasks[task_id]
                            if download_progress.get('status') == 'success':
                                task['titles'].remove(title)
                            elif download_progress.get('status') == 'error':
                                task['status'] = 'failed'
                                task['error'] = download_progress.get('message', '下载失败')
                            else:
                                task['progress'] = progress + (download_progress.get('progress', 0) / total_videos)
                            
                            task['last_update'] = datetime.now().isoformat()
                            self.save_tasks()
            
            # 如果没有出错且没有被标记为完成，则标记为完成
            with self.tasks_lock:
                task = self.tasks[task_id]
                if task['status'] not in ['completed', 'failed']:
                    task['status'] = 'completed'
                    task['progress'] = 100
                    task['last_update'] = datetime.now().isoformat()
                    self.save_tasks()

        except Exception as e:  # 确保每个 try 都有对应的 except
            logger.error(f"合集下载任务执行失败: {str(e)}")
            with self.tasks_lock:
                task = self.tasks[task_id]
                task['status'] = 'failed'
                task['error'] = str(e)
                task['last_update'] = datetime.now().isoformat()
                self.save_tasks()

    def create_task(self, bvid: str, output_dir: str, rename: bool = False) -> str:
        """创建新的下载任务"""
        task_id = f"{bvid}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 获取视频信息
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(f"https://www.bilibili.com/video/{bvid}", download=False)
                title = self.title_filter.filter_title(info.get('title', ''))
        except Exception as e:
            logger.error(f"获取视频信息失败: {str(e)}")
            title = ''
        
        task = {
            'task_id': task_id,
            'bvid': bvid,
            'title': title,
            'output_dir': output_dir,
            'rename': rename,
            'status': 'pending',
            'progress': 0,
            'created_at': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat()
        }
        
        with self.tasks_lock:
            self.tasks[task_id] = task
            self.save_tasks()
        
        # 在新线程中启动下载
        thread = threading.Thread(target=self._download_task, args=(task_id,))
        thread.daemon = True  # 设置为守护线程，这样主程序退出时线程会自动结束
        thread.start()
        
        return task_id

    def _download_task(self, task_id: str):
        """执行下载任务"""
        try:
            with self.tasks_lock:
                task = self.tasks[task_id]
                task['status'] = 'running'
                self.save_tasks()

            # 开始下载
            for progress in self.downloader.download(task['bvid'], task['output_dir'], task['rename']):
                if isinstance(progress, dict):
                    with self.tasks_lock:
                        task = self.tasks[task_id]
                        if progress.get('status') == 'success':
                            task['status'] = 'completed'
                        elif progress.get('status') == 'error':
                            task['status'] = 'failed'
                            task['error'] = progress.get('message', '下载失败')
                        else:
                            task['progress'] = progress.get('progress', 0)
                        
                        # 更新标题信息（应用过滤）
                        if title := progress.get('title'):
                            task['title'] = self.title_filter.filter_title(title)
                        
                        task['last_update'] = datetime.now().isoformat()
                        self.save_tasks()

            # 如果没有出错且没有被标记为完成，则标记为完成
            with self.tasks_lock:
                task = self.tasks[task_id]
                if task['status'] not in ['completed', 'failed']:
                    task['status'] = 'completed'
                    task['progress'] = 100
                    task['last_update'] = datetime.now().isoformat()
                    self.save_tasks()

        except Exception as e:  # 确保每个 try 都有对应的 except
            logger.error(f"下载任务执行失败: {str(e)}")
            with self.tasks_lock:
                task = self.tasks[task_id]
                task['status'] = 'failed'
                task['error'] = str(e)
                task['last_update'] = datetime.now().isoformat()
                self.save_tasks()

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """获取任务状态"""
        with self.tasks_lock:
            return self.tasks.get(task_id)

    def get_all_tasks(self) -> Dict[str, dict]:
        """获取所有任务"""
        with self.tasks_lock:
            return self.tasks.copy()

    def get_latest_task(self) -> Optional[dict]:
        """获取最新的任务"""
        with self.tasks_lock:
            if not self.tasks:
                return None
            # 按创建时间排序，返回最新的任务
            latest_task = max(self.tasks.values(), key=lambda x: x['created_at'])
            return latest_task.copy()

    def cleanup_completed_tasks(self):
        """清理已完成的任务"""
        with self.tasks_lock:
            completed_tasks = [
                task_id for task_id, task in self.tasks.items()
                if task['status'] in ['completed', 'failed']
            ]
            for task_id in completed_tasks:
                del self.tasks[task_id]
            self.save_tasks()
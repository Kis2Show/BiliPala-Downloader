import os
import json
import time
import logging
from datetime import datetime
import hashlib
from typing import Dict, Any, List, Optional
from .downloader import BiliDownloader
from .title_filter import TitleFilter
import yt_dlp

logger = logging.getLogger('TaskManager')

class TaskManager:
    def __init__(self):
        self.tasks_dir = "download_tasks"
        os.makedirs(self.tasks_dir, exist_ok=True)
        self.active_tasks = {}
        self._load_tasks()
        logger.info("任务管理器初始化完成")
        self.downloader = BiliDownloader()
        self.title_filter = TitleFilter()
        self.tasks_file = "download_tasks/active_tasks.json"
        self.load_tasks()
        
    def _load_tasks(self):
        """加载已有任务"""
        try:
            for filename in os.listdir(self.tasks_dir):
                if filename.endswith('.json'):
                    task_id = filename[:-5]  # 移除 .json 后缀
                    task_file = os.path.join(self.tasks_dir, filename)
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)
                        self.active_tasks[task_id] = task_data
            logger.info(f"加载了 {len(self.active_tasks)} 个任务")
        except Exception as e:
            logger.error(f"加载任务失败：{str(e)}")
    
    def _save_task(self, task_id: str):
        """保存任务到文件"""
        try:
            task_file = os.path.join(self.tasks_dir, f"{task_id}.json")
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(self.active_tasks[task_id], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存任务失败：{str(e)}")
    
    def create_task(self, bvid: str = None, series_id: str = None, output_dir: str = '', rename: bool = False, is_series: bool = False) -> str:
        """创建新任务"""
        try:
            # 生成任务ID
            task_id = hashlib.md5(f"{bvid or series_id}_{output_dir}_{time.time()}".encode()).hexdigest()
            
            # 创建任务数据
            task_data = {
                'created_at': datetime.now().isoformat(),
                'output_dir': output_dir,
                'rename': rename,
                'status': 'pending',
                'progress': 0,
                'error': None
            }
            
            # 根据任务类型添加特定信息
            if is_series:
                task_data.update({
                    'is_series': True,
                    'series_id': series_id,
                    'current_video': 0,
                    'total_videos': 0,
                    'series_progress': 0
                })
            else:
                task_data.update({
                    'is_series': False,
                    'bvid': bvid
                })
            
            self.active_tasks[task_id] = task_data
            self._save_task(task_id)
            
            logger.info(f"创建{'合集' if is_series else '视频'}任务：{task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"创建任务失败：{str(e)}")
            raise
    
    def update_task(self, task_id: str, progress_info: Dict[str, Any]):
        """更新任务状态"""
        try:
            if task_id not in self.active_tasks:
                logger.warning(f"任务不存在：{task_id}")
                return
            
            task = self.active_tasks[task_id]
            
            # 更新任务状态
            if 'status' in progress_info:
                task['status'] = progress_info['status']
            
            # 更新进度信息
            if task['is_series']:
                # 合集任务进度更新
                if 'series_progress' in progress_info:
                    task['series_progress'] = progress_info['series_progress']
                if 'current_video' in progress_info:
                    task['current_video'] = progress_info['current_video']
                if 'total_videos' in progress_info:
                    task['total_videos'] = progress_info['total_videos']
                if 'video_title' in progress_info:
                    task['current_video_title'] = progress_info['video_title']
            else:
                # 单视频任务进度更新
                if 'progress' in progress_info:
                    task['progress'] = progress_info['progress']
            
            # 更新标题
            if 'title' in progress_info:
                task['title'] = progress_info['title']
            
            # 更新错误信息
            if 'error' in progress_info:
                task['error'] = progress_info['error']
            
            # 如果任务完成或失败，记录完成时间
            if progress_info.get('status') in ['completed', 'failed']:
                task['completed_at'] = datetime.now().isoformat()
            
            self._save_task(task_id)
            
        except Exception as e:
            logger.error(f"更新任务状态失败：{str(e)}")
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        return self.active_tasks.get(task_id)
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """获取所有活动任务"""
        return list(self.active_tasks.values())
    
    def get_latest_task(self) -> Optional[Dict[str, Any]]:
        """获取最新任务"""
        if not self.active_tasks:
            return None
        
        # 按创建时间排序，返回最新的任务
        sorted_tasks = sorted(
            self.active_tasks.values(),
            key=lambda x: x.get('created_at', ''),
            reverse=True
        )
        return sorted_tasks[0] if sorted_tasks else None
    
    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """清理已完成的旧任务"""
        try:
            now = datetime.now()
            to_remove = []
            
            for task_id, task in self.active_tasks.items():
                if task.get('status') in ['completed', 'failed']:
                    completed_at = datetime.fromisoformat(task.get('completed_at', ''))
                    age = (now - completed_at).total_seconds() / 3600
                    
                    if age > max_age_hours:
                        to_remove.append(task_id)
            
            for task_id in to_remove:
                task_file = os.path.join(self.tasks_dir, f"{task_id}.json")
                if os.path.exists(task_file):
                    os.remove(task_file)
                del self.active_tasks[task_id]
            
            if to_remove:
                logger.info(f"清理了 {len(to_remove)} 个已完成的旧任务")
                
        except Exception as e:
            logger.error(f"清理任务失败：{str(e)}")

    def load_tasks(self):
        """加载保存的任务状态"""
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    saved_tasks = json.load(f)
                    self.active_tasks = saved_tasks
                logger.info(f"已加载 {len(self.active_tasks)} 个保存的任务")
        except Exception as e:
            logger.error(f"加载任务状态失败: {str(e)}")
            self.active_tasks = {}

    def save_tasks(self):
        """保存当前任务状态"""
        try:
            os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(self.active_tasks, f, ensure_ascii=False, indent=2)
            logger.info("任务状态已保存")
        except Exception as e:
            logger.error(f"保存任务状态失败: {str(e)}")

    def _download_task(self, task_id: str):
        """执行下载任务"""
        try:
            task = self.active_tasks[task_id]
            task['status'] = 'running'
            self._save_task(task_id)

            # 开始下载
            for progress in self.downloader.download(task['bvid'], task['output_dir'], task['rename']):
                if isinstance(progress, dict):
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
                    self._save_task(task_id)

            # 如果没有出错且没有被标记为完成，则标记为完成
            if task['status'] not in ['completed', 'failed']:
                task['status'] = 'completed'
                task['progress'] = 100
                task['last_update'] = datetime.now().isoformat()
                self._save_task(task_id)

        except Exception as e:
            logger.error(f"下载任务执行失败: {str(e)}")
            task['status'] = 'failed'
            task['error'] = str(e)
            task['last_update'] = datetime.now().isoformat()
            self._save_task(task_id) 
import os
import json
import hashlib
from typing import Dict, Optional
import logging
from datetime import datetime
import shutil
from threading import Lock
import tempfile

logger = logging.getLogger('FileManager')

class FileManager:
    def __init__(self, base_path: str = "downloads"):
        self.base_path = base_path
        self.metadata_file = os.path.join(base_path, "file_metadata.json")
        self.temp_dir = os.path.join(base_path, "temp")
        self.metadata_lock = Lock()
        
        # 创建必要的目录
        for path in [base_path, self.temp_dir]:
            os.makedirs(path, exist_ok=True)
            
        self.metadata = self._load_metadata()
        
    def _load_metadata(self) -> Dict:
        """加载元数据，如果文件损坏则尝试恢复"""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"加载元数据成功: {len(data)} 条记录")
                return data
        except json.JSONDecodeError:
            # 尝试恢复损坏的元数据文件
            backup_file = f"{self.metadata_file}.bak"
            if os.path.exists(backup_file):
                try:
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    logger.info(f"从备份恢复元数据: {len(data)} 条记录")
                    return data
                except:
                    pass
            logger.error("元数据文件损坏且无法恢复")
        except Exception as e:
            logger.error(f"加载元数据失败: {str(e)}")
        return {}
        
    def _save_metadata(self):
        """安全地保存元数据"""
        with self.metadata_lock:
            try:
                # 创建临时文件
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_file:
                    json.dump(self.metadata, temp_file, ensure_ascii=False, indent=2)
                
                # 备份当前文件
                if os.path.exists(self.metadata_file):
                    backup_file = f"{self.metadata_file}.bak"
                    shutil.copy2(self.metadata_file, backup_file)
                
                # 替换原文件
                shutil.move(temp_file.name, self.metadata_file)
                logger.info("元数据保存成功")
                
            except Exception as e:
                logger.error(f"保存元数据失败: {str(e)}")
                # 清理临时文件
                if 'temp_file' in locals():
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
            
    def check_file_exists(self, bvid: str, file_type: str) -> Optional[dict]:
        """检查文件是否存在且完整"""
        with self.metadata_lock:
            entry = self.metadata.get(bvid, {})
            file_path = entry.get(f'{file_type}_path')
            
            if not file_path or not os.path.exists(file_path):
                return None
                
            file_info = {
                'path': file_path,
                'size': os.path.getsize(file_path),
                'completed': False
            }
            
            # 检查元数据中的校验信息
            if checksum := entry.get('checksum'):
                current_size = os.path.getsize(file_path)
                if current_size == entry.get('file_size', 0):
                    if self.validate_file_integrity(file_path, checksum):
                        file_info['completed'] = True
                        return file_info
                file_info['existing_size'] = current_size
                
            return file_info

    def validate_file_integrity(self, file_path: str, expected_checksum: str) -> bool:
        """验证文件完整性"""
        if not os.path.exists(file_path):
            return False
            
        try:
            actual_checksum = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    actual_checksum.update(chunk)
                    
            return actual_checksum.hexdigest() == expected_checksum
        except Exception as e:
            logger.error(f"文件完整性验证失败: {str(e)}")
            return False

    def record_download_progress(self, bvid: str, file_type: str, chunk: bytes):
        """记录下载进度"""
        temp_path = self.get_temp_path(bvid, file_type)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        try:
            with open(temp_path, 'ab') as f:
                f.write(chunk)
        except Exception as e:
            logger.error(f"写入下载进度失败: {str(e)}")
            raise

    def get_temp_path(self, bvid: str, file_type: str) -> str:
        """获取临时文件路径"""
        return os.path.join(self.temp_dir, f"{bvid}_{file_type}.tmp")

    def update_file_metadata(self, bvid: str, file_type: str, final_path: str, checksum: str):
        """更新文件元数据"""
        with self.metadata_lock:
            self.metadata.setdefault(bvid, {})[f'{file_type}_path'] = final_path
            self.metadata[bvid]['checksum'] = checksum
            self.metadata[bvid]['file_size'] = os.path.getsize(final_path)
            self.metadata[bvid]['last_updated'] = datetime.now().isoformat()
            self._save_metadata()

    def store_file(self, file_type: str, content: bytes, bvid: str, metadata: Dict, append: bool = False) -> str:
        """存储文件并更新元数据"""
        # 生成文件名
        date_str = datetime.now().strftime("%Y%m%d")
        file_ext = {
            'video': '.mp4',
            'cover': '.jpg',
            'audio': '.mp3'
        }.get(file_type, '')
        
        if not file_ext:
            raise ValueError(f"不支持的文件类型: {file_type}")
        
        # 计算文件哈希
        content_hash = hashlib.md5(content).hexdigest()[:8]
        filename = f"{bvid}_{content_hash}{file_ext}"
        storage_path = os.path.join(self.base_path, date_str, file_type, filename)
        
        try:
            # 创建目录
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            
            # 写入文件
            mode = 'ab' if append else 'wb'
            with open(storage_path, mode) as f:
                f.write(content)
                
            # 更新元数据
            with self.metadata_lock:
                self.metadata[bvid] = {
                    'video_path': storage_path if file_type == 'video' else self.metadata.get(bvid, {}).get('video_path', ''),
                    'cover_path': storage_path if file_type == 'cover' else self.metadata.get(bvid, {}).get('cover_path', ''),
                    'audio_path': storage_path if file_type == 'audio' else self.metadata.get(bvid, {}).get('audio_path', ''),
                    'metadata': metadata,
                    'checksum': content_hash,
                    'file_size': os.path.getsize(storage_path),
                    'timestamp': datetime.now().isoformat()
                }
                self._save_metadata()
            
            return storage_path
            
        except Exception as e:
            logger.error(f"存储文件失败: {str(e)}")
            # 清理失败的文件
            if os.path.exists(storage_path):
                try:
                    os.remove(storage_path)
                except:
                    pass
            raise

    def get_pending_files(self) -> Dict:
        """获取待处理的文件"""
        with self.metadata_lock:
            return {k: v for k, v in self.metadata.items() if not v.get('processed')}

    def confirm_processing(self, bvid: str):
        """确认文件处理完成"""
        with self.metadata_lock:
            if bvid in self.metadata:
                self.metadata[bvid]['processed'] = True
                self.metadata[bvid]['processed_time'] = datetime.now().isoformat()
                self._save_metadata()

    def cleanup_temp_files(self, bvid: str):
        """清理临时文件"""
        try:
            with self.metadata_lock:
                if bvid in self.metadata:
                    # 删除临时文件
                    for file_type in ['video', 'cover']:
                        temp_path = self.get_temp_path(bvid, file_type)
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                            logger.info(f"清理临时文件: {temp_path}")
                    
                    # 删除元数据
                    del self.metadata[bvid]
                    self._save_metadata()
                    
        except Exception as e:
            logger.error(f"清理临时文件失败: {str(e)}")
            
    def __del__(self):
        """确保元数据被保存"""
        try:
            self._save_metadata()
        except:
            pass

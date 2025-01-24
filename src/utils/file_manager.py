import os
import json
import hashlib
from typing import Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger('FileManager')

class FileManager:
    def __init__(self, base_path: str = "downloads"):
        self.base_path = base_path
        self.metadata_file = os.path.join(base_path, "file_metadata.json")
        os.makedirs(base_path, exist_ok=True)
        self.metadata = self._load_metadata()
        
    def _load_metadata(self) -> Dict:
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载元数据失败: {str(e)}")
        return {}
        
    def _save_metadata(self):
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存元数据失败: {str(e)}")
            
    def check_file_exists(self, bvid: str, file_type: str) -> Optional[dict]:
        """检查文件是否存在且完整"""
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
        if entry.get('checksum') and entry.get('file_size'):
            current_size = os.path.getsize(file_path)
            if current_size == entry['file_size']:
                if self.validate_file_integrity(file_path, entry['checksum']):
                    file_info['completed'] = True
                    return file_info
            file_info['existing_size'] = current_size
            
        return file_info

    def validate_file_integrity(self, file_path: str, expected_checksum: str) -> bool:
        """验证文件完整性"""
        if not os.path.exists(file_path):
            return False
            
        actual_checksum = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                actual_checksum.update(chunk)
                
        return actual_checksum.hexdigest() == expected_checksum

    def record_download_progress(self, bvid: str, file_type: str, chunk: bytes):
        """记录下载进度（用于断点续传）"""
        temp_path = self.get_temp_path(bvid, file_type)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, 'ab') as f:  # 追加模式
            f.write(chunk)

    def get_temp_path(self, bvid: str, file_type: str) -> str:
        """获取临时文件路径"""
        return os.path.join(self.base_path, 'temp', f"{bvid}_{file_type}.tmp")

    def update_file_metadata(self, bvid: str, file_type: str, final_path: str, checksum: str):
        """更新最终文件元数据"""
        self.metadata.setdefault(bvid, {})[f'{file_type}_path'] = final_path
        self.metadata[bvid]['checksum'] = checksum
        self.metadata[bvid]['file_size'] = os.path.getsize(final_path)
        self._save_metadata()

    def store_file(self, file_type: str, content: bytes, bvid: str, metadata: Dict, append: bool = False) -> str:
        date_str = datetime.now().strftime("%Y%m%d")
        file_ext = {
            'video': '.mp4',
            'cover': '.jpg',
            'audio': '.mp3'
        }[file_type]
        
        filename = f"{bvid}_{hashlib.md5(content).hexdigest()[:8]}{file_ext}"
        storage_path = os.path.join(self.base_path, date_str, file_type, filename)
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        
        with open(storage_path, 'wb') as f:
            f.write(content)
            
        # 记录元数据关联
        self.metadata[bvid] = {
            'video_path': storage_path if file_type == 'video' else self.metadata.get(bvid, {}).get('video_path', ''),
            'cover_path': storage_path if file_type == 'cover' else self.metadata.get(bvid, {}).get('cover_path', ''),
            'audio_path': storage_path if file_type == 'audio' else self.metadata.get(bvid, {}).get('audio_path', ''),
            'metadata': metadata,
            'timestamp': datetime.now().isoformat()
        }
        self._save_metadata()
        
        return storage_path

    def get_pending_files(self) -> Dict:
        return {k:v for k,v in self.metadata.items() if not v.get('processed')}

    def confirm_processing(self, bvid: str):
        if bvid in self.metadata:
            self.metadata[bvid]['processed'] = True
            self._save_metadata()

    def cleanup_temp_files(self, bvid: str):
        if bvid in self.metadata:
            for file_type in ['video', 'cover']:
                path = self.metadata[bvid].get(f'{file_type}_path')
                if path and os.path.exists(path):
                    os.remove(path)
                    logger.info(f"清理临时文件: {path}")
            del self.metadata[bvid]
            self._save_metadata()

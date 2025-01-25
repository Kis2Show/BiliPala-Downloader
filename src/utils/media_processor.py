import os
import subprocess
import mutagen
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, APIC
from typing import Optional, Dict
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger('MediaProcessor')

class MediaProcessor:
    def __init__(self, ffmpeg_path: str = 'ffmpeg', max_workers: int = 4):
        self.ffmpeg_path = ffmpeg_path
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._verify_ffmpeg()
        
    def _verify_ffmpeg(self):
        """验证 FFmpeg 是否可用"""
        try:
            subprocess.run(
                [self.ffmpeg_path, '-version'],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            raise RuntimeError(f"FFmpeg 未安装或不可用: {str(e)}")
    
    def extract_audio(self,
                     input_path: str,
                     output_path: str,
                     metadata: Optional[Dict] = None,
                     cover_path: Optional[str] = None,
                     quality: str = '192k') -> bool:
        """转换音频格式并添加元数据"""
        try:
            # 创建输出目录
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 转码为MP3
            cmd = [
                self.ffmpeg_path,
                '-hide_banner',
                '-loglevel', 'error',
                '-i', input_path,
                '-c:a', 'libmp3lame',
                '-b:a', quality,
                '-map', 'a',
                '-vn',
                '-y',
                output_path
            ]
            
            # 执行转码
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg 转换失败: {result.stderr}")
                return False
            
            # 异步添加元数据和封面
            if metadata or cover_path:
                self._executor.submit(self.add_metadata, output_path, metadata, cover_path)
                
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg 转换失败: {str(e)}")
            # 清理失败的输出文件
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            raise RuntimeError(f"音频转换失败: {str(e)}") from e
            
        except Exception as e:
            logger.error(f"音频处理失败: {str(e)}")
            return False

    def add_metadata(self, 
                    mp3_path: str,
                    metadata: Optional[Dict],
                    cover_path: Optional[str] = None):
        """添加ID3元数据"""
        try:
            if not os.path.exists(mp3_path):
                logger.error(f"目标文件不存在: {mp3_path}")
                return
                
            audio = MP3(mp3_path, ID3=ID3)
            
            # 创建或更新标签
            if audio.tags is None:
                audio.add_tags()
                
            tags = audio.tags
            
            # 基础元数据
            if metadata:
                if title := metadata.get('title'):
                    tags.add(TIT2(encoding=3, text=title))
                if artist := metadata.get('artist'):
                    tags.add(TPE1(encoding=3, text=artist))
                if album := metadata.get('album'):
                    tags.add(TALB(encoding=3, text=album))
                if date := metadata.get('date'):
                    tags.add(TDRC(encoding=3, text=date))
                
            # 添加封面
            if cover_path and os.path.exists(cover_path):
                mime_type = 'image/jpeg' if cover_path.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
                
                try:
                    with open(cover_path, 'rb') as f:
                        cover_data = f.read()
                        tags.add(
                            APIC(
                                encoding=3,
                                mime=mime_type,
                                type=3,
                                desc='Cover',
                                data=cover_data
                            )
                        )
                    logger.info(f"成功添加封面: {os.path.basename(cover_path)}")
                except Exception as e:
                    logger.error(f"添加封面失败: {str(e)}")
                
            # 保存更改
            audio.save(v2_version=3)
            logger.info(f"元数据添加完成: {os.path.basename(mp3_path)}")
            
        except Exception as e:
            logger.error(f"元数据添加失败: {str(e)}")
            raise RuntimeError(f"无法添加元数据: {str(e)}") from e
        
    @staticmethod
    def validate_audio(file_path: str) -> bool:
        """验证音频文件完整性"""
        try:
            if not os.path.exists(file_path):
                return False
                
            # 检查文件大小
            if os.path.getsize(file_path) < 1024:  # 小于1KB的文件视为无效
                return False
                
            # 检查音频时长
            audio = MP3(file_path)
            return audio.info.length > 0
            
        except Exception as e:
            logger.error(f"音频验证失败: {str(e)}")
            return False
            
    def __del__(self):
        """清理资源"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)

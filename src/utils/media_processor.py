import os
import subprocess
import mutagen
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, APIC
from typing import Optional
import logging

logger = logging.getLogger('MediaProcessor')

class MediaProcessor:
    def __init__(self, ffmpeg_path: str = 'ffmpeg'):
        self.ffmpeg_path = ffmpeg_path
        
    def extract_audio(self,
                     input_path: str,
                     output_path: str,
                     metadata: Optional[dict] = None,
                     cover_path: Optional[str] = None) -> bool:
        """转换音频格式并添加元数据"""
        try:
            # 检查ffmpeg可用性
            subprocess.run([self.ffmpeg_path, '-version'], check=True, 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL)
            
            # 转码为MP3
            cmd = [
                self.ffmpeg_path,
                '-hide_banner',
                '-loglevel', 'error',
                '-i', input_path,
                '-q:a', '0',
                '-map', 'a',
                '-vn',
                '-y',
                output_path
            ]
            subprocess.run(cmd, check=True)
            
            # 添加元数据和封面
            if metadata or cover_path:
                self.add_metadata(output_path, metadata, cover_path)
                
            return True
        except FileNotFoundError as e:
            logger.error(f"FFmpeg未找到: {str(e)}")
            raise RuntimeError(f"FFmpeg未安装或不可用: {str(e)}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg转换失败: {str(e)}")
            raise RuntimeError(f"音频转换失败: {str(e)}") from e
        except Exception as e:
            logger.error(f"元数据处理失败: {str(e)}")
        return False

    def add_metadata(self, 
                    mp3_path: str,
                    metadata: Optional[dict],
                    cover_path: Optional[str] = None):
        """添加ID3元数据"""
        try:
            audio = MP3(mp3_path, ID3=ID3)
            
            # 创建或更新标签
            if audio.tags is None:
                audio.add_tags()
                
            tags = audio.tags
            
            # 基础元数据
            if metadata:
                tags.add(TIT2(encoding=3, text=metadata.get('title', '')))
                tags.add(TPE1(encoding=3, text=metadata.get('artist', '')))
                tags.add(TALB(encoding=3, text=metadata.get('album', '')))
                tags.add(TDRC(encoding=3, text=metadata.get('date', '')))
                
            # 添加封面（支持多种格式）
            if cover_path and os.path.exists(cover_path):
                _, ext = os.path.splitext(cover_path)
                mime_type = 'image/jpeg' if ext.lower() in ('.jpg', '.jpeg') else 'image/png'
                
                with open(cover_path, 'rb') as f:
                    cover_data = f.read()
                    tags.add(
                        APIC(
                            encoding=3,
                            mime=mime_type,
                            type=3,  # 封面图片
                            desc='Cover',
                            data=cover_data
                        )
                    )
                logger.info(f"成功添加封面: {os.path.basename(cover_path)}")
                
            audio.save(v2_version=3)  # 强制保存ID3v2.3格式确保兼容性
        except Exception as e:
            logger.error(f"元数据添加失败: {str(e)}")
            raise RuntimeError(f"无法添加元数据: {str(e)}") from e
        
    @staticmethod
    def validate_audio(file_path: str) -> bool:
        """验证音频文件完整性"""
        try:
            audio = MP3(file_path)
            return audio.info.length > 0
        except:
            return False

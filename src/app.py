from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from utils.task_manager import TaskManager
import os
import json
import logging
from datetime import datetime
import threading
from utils.downloader import BiliDownloader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('BiliDownloader-Web')

app = Flask(__name__)
task_manager = TaskManager()
downloader = BiliDownloader()

@app.route('/')
def index():
    logger.info("访问主页")
    return render_template('index.html')

@app.route('/check_playlist', methods=['POST'])
def check_playlist():
    try:
        data = request.get_json()
        bvid = data.get('bvid')
        if not bvid:
            return jsonify({'success': False, 'error': '缺少BV号'})
        
        count = downloader.check_playlist(bvid)
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        logger.error(f"检查播放列表失败：{str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download', methods=['POST'])
def start_download():
    try:
        data = request.get_json()
        bvid = data.get('bvid')
        output_dir = data.get('output_dir', '')
        rename = data.get('rename', False)
        
        if not bvid or not output_dir:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        
        # 创建任务
        task_id = task_manager.create_task(bvid=bvid, output_dir=output_dir, rename=rename)
        
        # 启动下载线程
        def download_thread():
            try:
                for progress in downloader.download(bvid, output_dir, rename):
                    task_manager.update_task(task_id, progress)
            except Exception as e:
                logger.error(f"下载失败：{str(e)}")
                task_manager.update_task(task_id, {
                    'status': 'failed',
                    'error': str(e)
                })
        
        thread = threading.Thread(target=download_thread)
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '下载任务已创建'
        })
        
    except Exception as e:
        logger.error(f"创建下载任务失败：{str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download_series', methods=['POST'])
def start_series_download():
    try:
        data = request.get_json()
        url = data.get('url')
        output_dir = data.get('output_dir', '')
        rename = data.get('rename', False)
        
        if not url or not output_dir:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        
        # 验证是否为合集链接
        if not downloader.is_series_url(url):
            return jsonify({'success': False, 'error': '无效的合集链接'})
        
        # 解析合集信息
        uid, sid = downloader.extract_series_info(url)
        
        # 创建合集任务
        task_id = task_manager.create_task(
            series_id=sid,
            output_dir=output_dir,
            rename=rename,
            is_series=True
        )
        
        # 启动下载线程
        def download_series_thread():
            try:
                for progress in downloader.download_series(url, output_dir, rename):
                    # 更新任务状态，添加合集相关信息
                    progress.update({
                        'series_id': sid,
                        'is_series': True
                    })
                    task_manager.update_task(task_id, progress)
            except Exception as e:
                logger.error(f"合集下载失败：{str(e)}")
                task_manager.update_task(task_id, {
                    'status': 'failed',
                    'error': str(e),
                    'series_id': sid,
                    'is_series': True
                })
        
        thread = threading.Thread(target=download_series_thread)
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '合集下载任务已创建'
        })
        
    except Exception as e:
        logger.error(f"创建合集下载任务失败：{str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/task_status', methods=['GET'])
def task_status():
    task_id = request.args.get('task_id')
    if not task_id:
        return jsonify({'error': '缺少task_id参数'}), 400
    
    status = task_manager.get_task(task_id)
    if not status:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify(status)

@app.route('/active_tasks', methods=['GET'])
def get_active_tasks():
    """获取所有活动任务"""
    tasks = task_manager.get_active_tasks()
    return jsonify({'tasks': tasks})

@app.route('/latest_task', methods=['GET'])
def latest_task():
    """获取最新的任务"""
    task = task_manager.get_latest_task()
    if not task:
        return jsonify({'error': '没有找到任务'}), 404
    return jsonify(task)

@app.route('/cleanup_tasks', methods=['POST'])
def cleanup_tasks():
    """清理已完成的任务"""
    task_manager.cleanup_completed_tasks()
    return jsonify({'success': True, 'message': '已清理完成的任务'})

if __name__ == '__main__':
    logger.info("启动 Web 服务器")
    # 确保下载任务目录存在
    os.makedirs('download_tasks', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)

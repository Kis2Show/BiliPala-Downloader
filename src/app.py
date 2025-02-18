from flask import Flask, render_template, request, jsonify, Response
from utils.task_manager import TaskManager
from utils.title_filter import TitleFilter
import os
import json
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('BiliDownloader-Web')

app = Flask(__name__)
task_manager = TaskManager()
title_filter = TitleFilter()

@app.route('/')
def index():
    logger.info("访问主页")
    return render_template('index.html')

@app.route('/check_playlist', methods=['POST'])
def check_playlist():
    data = request.get_json()
    bvid = data.get('bvid')
    logger.info(f"检查播放列表：{bvid}")
    try:
        count = task_manager.downloader.check_playlist(bvid)
        logger.info(f"播放列表检查完成：{count} 个视频")
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        logger.error(f"播放列表检查失败：{str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    bvid = data.get('bvid')
    output_dir = data.get('output_dir')
    rename = data.get('rename', False)
    
    if not bvid or not output_dir:
        logger.error("下载请求缺少必要参数")
        return jsonify({'error': '缺少必要参数'}), 400
    
    logger.info(f"开始下载任务：bvid={bvid}, output_dir={output_dir}, rename={rename}")
    
    try:
        # 创建新任务
        task_id = task_manager.create_task(bvid, output_dir, rename)
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '任务已创建并开始下载'
        })
    except Exception as e:
        logger.error(f"创建下载任务失败：{str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/task_status', methods=['GET'])
def task_status():
    task_id = request.args.get('task_id')
    if not task_id:
        return jsonify({'error': '缺少task_id参数'}), 400
    
    status = task_manager.get_task_status(task_id)
    if not status:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify(status)

@app.route('/active_tasks', methods=['GET'])
def get_active_tasks():
    """获取所有活动任务"""
    tasks = task_manager.get_all_tasks()
    return jsonify({'tasks': list(tasks.values())})

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

@app.route('/filter_rules', methods=['GET', 'POST'])
def filter_rules():
    """获取或更新过滤规则"""
    if request.method == 'GET':
        return jsonify(title_filter.get_config())
    else:
        try:
            rules = request.get_json()
            title_filter.remove_chars = rules.get('remove_chars', [])
            title_filter.remove_words = rules.get('remove_words', [])
            title_filter.replace_rules = rules.get('replace_rules', [])
            title_filter.save_config()
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"保存过滤规则失败：{str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("启动 Web 服务器")
    # 确保下载任务目录存在
    os.makedirs('download_tasks', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)

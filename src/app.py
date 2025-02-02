from flask import Flask, render_template, request, jsonify, Response
import requests
from utils.task_manager import TaskManager
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

@app.route('/')
def index():
    logger.info("访问主页")
    return render_template('index.html')

@app.route('/check_playlist', methods=['POST'])
def check_playlist():
    """检查播放列表或合集信息"""
    data = request.get_json()
    params = data.get('params', {})

    if not params:
        logger.error("请求缺少 params 参数")
        return jsonify({'success': False, 'message': '请求必须包含 params 参数'}), 400

    if 'mid' in params and 'season_id' in params:
        # 处理合集
        mid = params['mid']
        season_id = params['season_id']
        try:
            result = task_manager.downloader.get_collection_info(mid, season_id)
            return jsonify({'success': True, 'data': {'type': 'collection', 'count': len(result)}})
        
        except Exception as e:
            logger.error(f"获取合集信息失败：{str(e)}")
            return jsonify({'success': False, 'message': '获取合集信息失败'}), 500
        
    elif 'bvid' in params:
        # 处理单个视频
        bvid = params['bvid']
        try:
            result = task_manager.downloader.check_playlist([bvid])
            return jsonify({'success': True, 'data': {'type': 'video', 'count': result['count']}})
        except Exception as e:
            logger.error(f"检查播放列表失败：{str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500
    else:
        logger.error("无效的 params 参数")
        return jsonify({'success': False, 'message': 'params 必须包含 mid 和 season_id 或 bvid'}), 400

@app.route('/download', methods=['POST'])
def download():
    """处理下载请求（合集或普通视频）"""
    data = request.get_json()
    if not data:
        logger.error("请求体为空或不是有效的 JSON 数据")
        return jsonify({'error': '请求体为空或不是有效的 JSON 数据'}), 400
    
    bvid = data.get('bvid')
    mid = data.get('mid')
    season_id = data.get('season_id')
    is_collection = False
    output_dir = data.get('output_dir')
    rename = data.get('rename', False)

    if not output_dir:
        logger.error("下载请求缺少输出目录参数")
        return jsonify({'error': '缺少输出目录参数'}), 400  

    if mid and season_id:
        is_collection = True
    else:
        is_collection = False

    try:
        if is_collection:
            # 合集下载
            if not mid or not season_id:
                logger.error("合集下载缺少必要参数")
                return jsonify({'error': '合集下载缺少必要参数'}), 400

            logger.info(f"开始合集下载任务：mid={mid}, season_id={season_id}, output_dir={output_dir}, rename={rename}")

            # 创建合集下载任务
            task_id = task_manager.create_collection_task(mid, season_id, output_dir, rename)
            return jsonify({
                'success': True,
                'task_id': task_id,
                'message': '合集下载任务已创建并开始下载'
            })
        else:
            # 普通下载
            if not bvid:
                logger.error("普通下载缺少必要参数")
                return jsonify({'error': '普通下载缺少必要参数'}), 400

            logger.info(f"开始普通下载任务：bvid={bvid}, output_dir={output_dir}, rename={rename}")

            # 创建普通下载任务
            task_id = task_manager.create_task(bvid, output_dir, rename)
            return jsonify({
                'success': True,
                'task_id': task_id,
                'message': '下载任务已创建并开始下载'
            })
    except Exception as e:
        logger.error(f"创建下载任务失败：{str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/task_status', methods=['GET'])
def task_status():
    """获取任务状态"""
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
    # logger.info(f"所有活动任务：{tasks}")
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

if __name__ == '__main__':
    logger.info("启动 Web 服务器")
    # 确保下载任务目录存在
    os.makedirs('download_tasks', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
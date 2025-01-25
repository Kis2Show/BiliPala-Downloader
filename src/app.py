from flask import Flask, render_template, request, jsonify, Response
from utils.downloader import BiliDownloader
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
downloader = BiliDownloader()

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
        count = downloader.check_playlist(bvid)
        logger.info(f"播放列表检查完成：{count} 个视频")
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        logger.error(f"播放列表检查失败：{str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download', methods=['GET'])
def download():
    bvid = request.args.get('bvid')
    output_dir = request.args.get('output_dir')
    rename = request.args.get('rename', 'false').lower() == 'true'
    
    if not bvid or not output_dir:
        logger.error("下载请求缺少必要参数")
        return jsonify({'error': '缺少必要参数'}), 400
    
    logger.info(f"开始下载任务：bvid={bvid}, output_dir={output_dir}, rename={rename}")
    
    # 创建新任务记录
    task_id = f"{bvid}_{output_dir}"
    new_task = {
        'task_id': task_id,
        'bvid': bvid,
        'output_dir': output_dir,
        'rename': rename,
        'status': 'pending',
        'progress': 0,
        'last_update': datetime.now().isoformat()
    }
    
    # 保存任务记录
    history = load_download_history()
    history['tasks'].append(new_task)
    save_download_history(history)
    
    def generate():
        try:
            for progress in downloader.download(bvid, output_dir, rename):
                # 更新任务状态
                history = load_download_history()
                for task in history['tasks']:
                    if task['task_id'] == task_id:
                        task['status'] = progress.get('status', 'running')
                        task['progress'] = progress.get('progress', 0)
                        task['last_update'] = datetime.now().isoformat()
                        break
                save_download_history(history)
                
                yield f"data: {json.dumps(progress)}\n\n"
        except Exception as e:
            # 更新任务状态为失败
            history = load_download_history()
            for task in history['tasks']:
                if task['task_id'] == task_id:
                    task['status'] = 'failed'
                    task['last_update'] = datetime.now().isoformat()
                    break
            save_download_history(history)
            
            logger.error(f"下载过程出错：{str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/task_status', methods=['GET'])
def task_status():
    task_id = request.args.get('task_id')
    if not task_id:
        return jsonify({'error': '缺少task_id参数'}), 400
    
    status = downloader.load_task_state(task_id)
    if not status:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify(status)
def load_download_history():
    try:
        with open('download_tasks/download_history.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'tasks': []}

def save_download_history(data):
    with open('download_tasks/download_history.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/download_history', methods=['GET'])
def get_download_history():
    history = load_download_history()
    # 只返回未完成的任务
    active_tasks = [task for task in history['tasks'] if task['status'] != 'completed']
    return jsonify({'tasks': active_tasks})

@app.route('/update_task_status', methods=['POST'])
def update_task_status():
    data = request.get_json()
    task_id = data.get('task_id')
    status = data.get('status')
    progress = data.get('progress')
    
    if not task_id or not status:
        return jsonify({'error': '缺少必要参数'}), 400
    
    history = load_download_history()
    for task in history['tasks']:
        if task['task_id'] == task_id:
            task['status'] = status
            if progress is not None:
                task['progress'] = progress
            task['last_update'] = datetime.now().isoformat()
            break
    else:
        return jsonify({'error': '任务不存在'}), 404
    
    save_download_history(history)
    return jsonify({'success': True})

@app.route('/latest_task', methods=['GET'])
def latest_task():
    try:
        # 获取最新的任务文件
        task_files = sorted(
            [f for f in os.listdir('download_tasks') if f.endswith('.json')],
            key=lambda f: os.path.getmtime(os.path.join('download_tasks', f)),
            reverse=True
        )
        if not task_files:
            return jsonify({'error': '没有找到任务'}), 404
        
        latest_file = task_files[0]
        with open(os.path.join('download_tasks', latest_file), 'r', encoding='utf-8') as f:
            task_data = json.load(f)
        
        return jsonify({
            'bvid': task_data.get('bvid'),
            'output_dir': task_data.get('output_dir'),
            'status': task_data.get('status'),
            'progress': task_data.get('progress', 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("启动 Web 服务器")
    app.run(host='0.0.0.0', port=5000, debug=True)

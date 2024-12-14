from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import yt_dlp
import os
import json
from pathlib import Path
import asyncio

app = FastAPI()

# 挂载静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 确保下载目录存在
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# 存储下载状态
download_status = {}

# 添加对下载目录的访问支持
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

def get_video_info(url: str):
    """获取视频信息"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title'),
                'duration': info.get('duration'),
                'uploader': info.get('uploader'),
                'description': info.get('description'),
            }
        except Exception as e:
            return None

async def download_video(url: str, video_id: str):
    """异步下载视频"""
    download_status[video_id] = {'progress': 0, 'status': 'downloading'}
    
    def progress_hook(d):
        if d['status'] == 'downloading':
            download_status[video_id]['progress'] = float(d.get('_percent_str', '0%').replace('%', ''))
        elif d['status'] == 'finished':
            download_status[video_id]['status'] = 'finished'

    ydl_opts = {
        'format': 'best',
        'outtmpl': str(DOWNLOAD_DIR / '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        download_status[video_id]['status'] = 'error'
        download_status[video_id]['error'] = str(e)

@app.get("/")
async def home(request: Request):
    """主页面"""
    videos = []
    for file in DOWNLOAD_DIR.glob("*"):
        if file.suffix in ['.mp4', '.webm', '.mkv']:
            videos.append({
                'title': file.stem,
                'path': str(file),
                'size': f"{file.stat().st_size / (1024*1024):.2f} MB"
            })
    
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "videos": videos}
    )

@app.post("/download")
async def download(url: str, background_tasks: BackgroundTasks):
    """处理下载请求"""
    video_info = get_video_info(url)
    if not video_info:
        return JSONResponse({"error": "无法获取视频信息"}, status_code=400)
    
    video_id = str(hash(url))
    background_tasks.add_task(download_video, url, video_id)
    
    return {"video_id": video_id, "info": video_info}

@app.get("/status/{video_id}")
async def get_status(video_id: str):
    """获取下载状态"""
    return download_status.get(video_id, {'status': 'not_found'})

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port) 
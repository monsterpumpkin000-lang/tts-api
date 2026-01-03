from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uuid, os, subprocess, requests, math, logging, shutil
import edge_tts
from typing import Dict

# =========================
# APP INIT
# =========================
app = FastAPI(title="US Shorts Render API")
logging.basicConfig(level=logging.INFO)

BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").rstrip("/")
if not BASE_URL.startswith("http"):
    BASE_URL = "https://" + BASE_URL

AUDIO_DIR = "audio"
VIDEO_DIR = "output"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
app.mount("/output", StaticFiles(directory=VIDEO_DIR), name="output")

# =========================
# IN-MEMORY JOB STORE
# =========================
RENDER_JOBS: Dict[str, dict] = {}

# =========================
# 1. SCRIPT GENERATOR
# =========================
class ScriptRequest(BaseModel):
    theme: str
    audience: str

@app.post("/generate-script")
async def generate_script(req: ScriptRequest):
    hook = "Small daily habits build unshakable confidence."
    body = "Consistency beats motivation when motivation fades."
    ending = "Start today. Stay consistent."

    return {
        "voice_text": f"{hook} {body} {ending}",
        "subtitle_text": f"{hook} {body}",
        "video_query": "cinematic calm nature"
    }

# =========================
# 2. TTS
# =========================
class TTSRequest(BaseModel):
    text: str

@app.post("/tts")
async def tts(req: TTSRequest):
    filename = f"{uuid.uuid4().hex}.mp3"
    path = os.path.join(AUDIO_DIR, filename)

    communicate = edge_tts.Communicate(
        text=req.text,
        voice="en-US-JennyNeural"
    )
    await communicate.save(path)

    duration = max(3, math.ceil(len(req.text.split()) * 0.45))

    return {
        "audio_url": f"{BASE_URL}/audio/{filename}",
        "duration": duration
    }

# =========================
# 3. STOCK VIDEO (PEXELS)
# =========================
class StockVideoRequest(BaseModel):
    query: str

@app.post("/get-stock-video")
async def get_stock_video(req: StockVideoRequest):
    headers = {
        "Authorization": os.getenv("PEXELS_API_KEY", "")
    }

    url = (
        "https://api.pexels.com/videos/search"
        f"?query={req.query}&orientation=portrait&per_page=1"
    )

    res = requests.get(url, headers=headers, timeout=20)
    res.raise_for_status()
    data = res.json()

    return {
        "video_url": data["videos"][0]["video_files"][0]["link"]
    }

# =========================
# 4. RENDER VIDEO (ASYNC)
# =========================
class RenderRequest(BaseModel):
    video_url: str
    audio_url: str
    subtitle_text: str

@app.post("/render-video/start")
async def start_render(req: RenderRequest):
    job_id = uuid.uuid4().hex

    RENDER_JOBS[job_id] = {
        "status": "processing",
        "video_url": None,
        "error": None
    }

    run_render_job(job_id, req)

    return {
        "job_id": job_id,
        "status": "processing"
    }

@app.get("/render-video/status/{job_id}")
async def render_status(job_id: str):
    job = RENDER_JOBS.get(job_id)
    if not job:
        return {"status": "not_found"}
    return job

# =========================
# BACKGROUND RENDER WORKER
# =========================
def run_render_job(job_id: str, req: RenderRequest):
    video_path = f"/tmp/{uuid.uuid4().hex}.mp4"
    audio_path = f"/tmp/{uuid.uuid4().hex}.mp3"
    output_filename = f"{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(VIDEO_DIR, output_filename)

    try:
        # Validate ffmpeg
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg not found in PATH")

        logging.info(f"[{job_id}] Downloading video")
        v = requests.get(req.video_url, timeout=60)
        v.raise_for_status()

        logging.info(f"[{job_id}] Downloading audio")
        a = requests.get(req.audio_url, timeout=60)
        a.raise_for_status()

        with open(video_path, "wb") as f:
            f.write(v.content)

        with open(audio_path, "wb") as f:
            f.write(a.content)

        logging.info(f"[{job_id}] Running ffmpeg")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-shortest",
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            output_path
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        RENDER_JOBS[job_id]["status"] = "finished"
        RENDER_JOBS[job_id]["video_url"] = (
            f"{BASE_URL}/output/{output_filename}"
        )

        logging.info(f"[{job_id}] Render completed")

    except Exception as e:
        logging.exception(f"[{job_id}] Render failed")
        RENDER_JOBS[job_id]["status"] = "error"
        RENDER_JOBS[job_id]["error"] = str(e)

# =========================
# ENTRYPOINT (RAILWAY SAFE)
# =========================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )

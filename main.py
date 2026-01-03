from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uuid, os, subprocess, requests, math, logging, shutil
import edge_tts
from typing import Dict

# =========================
# APP INIT
# =========================
logging.basicConfig(level=logging.INFO)

app = FastAPI()

BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
if BASE_URL and not BASE_URL.startswith("http"):
    BASE_URL = "https://" + BASE_URL
BASE_URL = BASE_URL.rstrip("/")

AUDIO_DIR = "audio"
VIDEO_DIR = "output"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
app.mount("/output", StaticFiles(directory=VIDEO_DIR), name="output")

# =========================
# HEALTH CHECK (WAJIB)
# =========================
@app.get("/")
def health():
    return {"status": "ok"}

# =========================
# IN-MEMORY JOB STORE
# =========================
RENDER_JOBS: Dict[str, dict] = {}

# =========================
# 1. SCRIPT
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
# 3. STOCK VIDEO
# =========================
class StockVideoRequest(BaseModel):
    query: str

@app.post("/get-stock-video")
async def get_stock_video(req: StockVideoRequest):
    headers = {"Authorization": os.getenv("PEXELS_API_KEY", "")}
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
# 4. RENDER VIDEO
# =========================
class RenderRequest(BaseModel):
    video_url: str
    audio_url: str
    subtitle_text: str

@app.post("/render-video/start")
async def start_render(req: RenderRequest, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex

    RENDER_JOBS[job_id] = {
        "status": "pending",
        "video_url": None,
        "error": None
    }

    background_tasks.add_task(run_render_job, job_id, req)

    return {"job_id": job_id, "status": "started"}

@app.get("/render-video/status/{job_id}")
def render_status(job_id: str):
    return RENDER_JOBS.get(job_id, {"status": "not_found"})

# =========================
# BACKGROUND WORKER
# =========================
def run_render_job(job_id: str, req: RenderRequest):
    try:
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise RuntimeError("ffmpeg not found in PATH")

        video_tmp = f"/tmp/{uuid.uuid4().hex}.mp4"
        audio_tmp = f"/tmp/{uuid.uuid4().hex}.mp3"
        output_path = os.path.join(VIDEO_DIR, f"{uuid.uuid4().hex}.mp4")

        with open(video_tmp, "wb") as f:
            f.write(requests.get(req.video_url, timeout=60).content)

        with open(audio_tmp, "wb") as f:
            f.write(requests.get(req.audio_url, timeout=60).content)

        cmd = [
            ffmpeg_path, "-y",
            "-i", video_tmp,
            "-i", audio_tmp,
            "-shortest",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            output_path
        ]

        subprocess.run(cmd, check=True)

        RENDER_JOBS[job_id]["status"] = "finished"
        RENDER_JOBS[job_id]["video_url"] = f"{BASE_URL}/output/{os.path.basename(output_path)}"

    except Exception as e:
        logging.exception("Render failed")
        RENDER_JOBS[job_id]["status"] = "error"
        RENDER_JOBS[job_id]["error"] = str(e)

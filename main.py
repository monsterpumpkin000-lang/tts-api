from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uuid, os, subprocess, requests, math, logging, shutil
from typing import Dict

logging.basicConfig(level=logging.INFO)
app = FastAPI()

# =========================
# HEALTH CHECK (WAJIB)
# =========================
@app.get("/")
def health():
    return {"status": "ok"}

# =========================
# BASE CONFIG
# =========================
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
# JOB STORE
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
    return {
        "voice_text": "Small daily habits build unshakable confidence.",
        "subtitle_text": "Small daily habits build confidence.",
        "video_query": "cinematic calm nature"
    }

# =========================
# 2. TTS (LAZY LOAD EDGE-TTS)
# =========================
class TTSRequest(BaseModel):
    text: str

@app.post("/tts")
async def tts(req: TTSRequest):
    import edge_tts  # ⬅️ PENTING: LAZY LOAD

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
def get_stock_video(req: StockVideoRequest):
    headers = {"Authorization": os.getenv("PEXELS_API_KEY", "")}
    url = f"https://api.pexels.com/videos/search?query={req.query}&orientation=portrait&per_page=1"

    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()

    return {"video_url": data["videos"][0]["video_files"][0]["link"]}

# =========================
# 4. RENDER VIDEO
# =========================
class RenderRequest(BaseModel):
    video_url: str
    audio_url: str
    subtitle_text: str

@app.post("/render-video/start")
def start_render(req: RenderRequest, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex
    RENDER_JOBS[job_id] = {"status": "pending", "video_url": None, "error": None}
    background_tasks.add_task(run_render_job, job_id, req)
    return {"job_id": job_id}

@app.get("/render-video/status/{job_id}")
def render_status(job_id: str):
    return RENDER_JOBS.get(job_id, {"status": "not_found"})

def run_render_job(job_id: str, req: RenderRequest):
    try:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found")

        vtmp = f"/tmp/{uuid.uuid4().hex}.mp4"
        atmp = f"/tmp/{uuid.uuid4().hex}.mp3"
        out = os.path.join(VIDEO_DIR, f"{uuid.uuid4().hex}.mp4")

        open(vtmp, "wb").write(requests.get(req.video_url, timeout=30).content)
        open(atmp, "wb").write(requests.get(req.audio_url, timeout=30).content)

        subprocess.run([
            ffmpeg, "-y",
            "-i", vtmp,
            "-i", atmp,
            "-shortest",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            out
        ], check=True)

        RENDER_JOBS[job_id]["status"] = "finished"
        RENDER_JOBS[job_id]["video_url"] = f"{BASE_URL}/output/{os.path.basename(out)}"

    except Exception as e:
        logging.exception("render failed")
        RENDER_JOBS[job_id]["status"] = "error"
        RENDER_JOBS[job_id]["error"] = str(e)

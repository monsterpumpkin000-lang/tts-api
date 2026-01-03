from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uuid, os, subprocess, requests, random, math
import edge_tts

app = FastAPI()

BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").rstrip("/")
AUDIO_DIR = "audio"
VIDEO_DIR = "output"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
app.mount("/output", StaticFiles(directory=VIDEO_DIR), name="output")


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

   PUBLIC_BASE = os.getenv("RAILWAY_PUBLIC_DOMAIN")

if not PUBLIC_BASE.startswith("http"):
    PUBLIC_BASE = "https://" + PUBLIC_BASE

return {
    "audio_url": f"{PUBLIC_BASE}/audio/{filename}",
    "duration": duration
}


# =========================
# 3. STOCK VIDEO
# =========================
class StockVideoRequest(BaseModel):
    query: str

@app.post("/get-stock-video")
async def get_stock_video(req: StockVideoRequest):
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    url = f"https://api.pexels.com/videos/search?query={req.query}&orientation=portrait&per_page=1"
    res = requests.get(url, headers=headers, timeout=20)
    res.raise_for_status()
    data = res.json()
    return {"video_url": data["videos"][0]["video_files"][0]["link"]}


# =========================
# 4. RENDER VIDEO (FIXED & SAFE)
# =========================
import logging
logging.basicConfig(level=logging.INFO)

class RenderRequest(BaseModel):
    video_url: str
    audio_url: str
    subtitle_text: str

@app.post("/render-video")
async def render_video(req: RenderRequest):
    video_path = f"/tmp/{uuid.uuid4().hex}.mp4"
    audio_path = f"/tmp/{uuid.uuid4().hex}.mp3"
    output_path = os.path.join(VIDEO_DIR, f"{uuid.uuid4().hex}.mp4")

    try:
        # ---- LOG INPUT ----
        logging.info(f"VIDEO URL: {req.video_url}")
        logging.info(f"AUDIO URL: {req.audio_url}")
        logging.info(f"SUBTITLE LEN: {len(req.subtitle_text)}")

        # ---- DOWNLOAD FILES ----
        v_res = requests.get(req.video_url, timeout=30)
        a_res = requests.get(req.audio_url, timeout=30)

        v_res.raise_for_status()
        a_res.raise_for_status()

        with open(video_path, "wb") as f:
            f.write(v_res.content)

        with open(audio_path, "wb") as f:
            f.write(a_res.content)

        # ---- VALIDATE FILE SIZE ----
        if os.path.getsize(video_path) == 0:
            raise Exception("Downloaded video is empty")

        if os.path.getsize(audio_path) == 0:
            raise Exception("Downloaded audio is empty")

        logging.info(f"Video size: {os.path.getsize(video_path)}")
        logging.info(f"Audio size: {os.path.getsize(audio_path)}")

        # ---- FFMPEG ----
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-shortest",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
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
            logging.error(result.stderr)
            raise Exception("FFmpeg failed")

        return {
            "video_url": f"{BASE_URL}/output/{os.path.basename(output_path)}"
        }

    except Exception as e:
        logging.exception("Render failed")
        return {"error": str(e)}

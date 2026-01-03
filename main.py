from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uuid, os, subprocess, requests, math
import edge_tts

# =========================
# APP INIT
# =========================
app = FastAPI()

BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").rstrip("/")
AUDIO_DIR = "audio"
VIDEO_DIR = "output"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
app.mount("/output", StaticFiles(directory=VIDEO_DIR), name="output")

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
# 2. TEXT TO SPEECH (URL)
# =========================
class TTSRequest(BaseModel):
    text: str

@app.post("/tts")
async def tts(req: TTSRequest):
    filename = f"{uuid.uuid4().hex}.mp3"
    path = os.path.join(AUDIO_DIR, filename)

    communicate = edge_tts.Communicate(
        text=req.text,
        voice="en-US-JennyNeural",
        rate="+8%",
        pitch="+0Hz"
    )
    await communicate.save(path)

    words = len(req.text.split())
    duration = max(4, math.ceil(words * 0.45))

    return {
        "audio_url": f"{BASE_URL}/audio/{filename}",
        "duration": duration
    }

# =========================
# 3. GET STOCK VIDEO
# =========================
class StockVideoRequest(BaseModel):
    query: str

@app.post("/get-stock-video")
async def get_stock_video(req: StockVideoRequest):
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}

    url = (
        "https://api.pexels.com/videos/search"
        f"?query={req.query}&orientation=portrait&per_page=1"
    )

    res = requests.get(url, headers=headers, timeout=20)
    res.raise_for_status()

    data = res.json()
    return {"video_url": data["videos"][0]["video_files"][0]["link"]}

# =========================
# 4. RENDER VIDEO (STABLE)
# =========================
class RenderRequest(BaseModel):
    video_url: str
    audio_url: str
    subtitle_text: str

@app.post("/render-video")
async def render_video(req: RenderRequest):
    video_path = f"/tmp/{uuid.uuid4().hex}.mp4"
    audio_path = f"/tmp/{uuid.uuid4().hex}.mp3"
    output_file = f"{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(VIDEO_DIR, output_file)

    # Download assets
   def download_file(url, path):
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    # SAFE & FAST PRESET
    vf = (
    "scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920,"
    "eq=contrast=1.05:saturation=1.08:brightness=0.02"
)


    cmd = [
    "ffmpeg", "-y",
    "-loglevel", "error",
    "-i", video_path,
    "-i", audio_path,
    "-map", "0:v:0",
    "-map", "1:a:0",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-crf", "28",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    "-shortest",
    "-vf", vf,
    "-c:a", "aac",
    "-b:a", "128k",
    output_path
]

    return {
        "video_url": f"{BASE_URL}/output/{output_file}"
    }

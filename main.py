from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import uuid, os, subprocess, requests, random
import edge_tts

app = FastAPI()

# =====================================================
# GLOBAL DIRECTORIES (PUBLIC ASSETS)
# =====================================================
BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "public" / "audio"
VIDEO_DIR = BASE_DIR / "public" / "video"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
app.mount("/video", StaticFiles(directory=VIDEO_DIR), name="video")

PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")

# =====================================================
# 1. SCRIPT GENERATOR
# =====================================================
class ScriptRequest(BaseModel):
    theme: str
    angle: str
    core_truth: str
    emotion: str
    audience: str

@app.post("/generate-script")
async def generate_script(req: ScriptRequest):
    hook = "Small daily habits build unshakable confidence."
    body = "Consistency beats motivation when motivation fades."
    ending = "Start today. Stay consistent."

    return {
        "voice_text": f"{hook} {body} {ending}",
        "subtitle_text": f"{hook} {body}",
        "video_query": "cinematic calm determination",
    }

# =====================================================
# 2. TEXT TO SPEECH (EDGE TTS → URL)
# =====================================================
class TTSRequest(BaseModel):
    text: str

@app.post("/tts")
async def tts(req: TTSRequest):
    audio_id = uuid.uuid4().hex
    audio_path = AUDIO_DIR / f"{audio_id}.mp3"

    communicate = edge_tts.Communicate(
        text=req.text,
        voice="en-US-JennyNeural",
        rate="+10%",
        pitch="+0Hz",
    )
    await communicate.save(str(audio_path))

    words = len(req.text.split())
    duration = max(3, int(words / 2.3))

    return {
        "audio_url": f"https://{PUBLIC_DOMAIN}/audio/{audio_id}.mp3",
        "duration": duration,
    }

# =====================================================
# 3. GET STOCK VIDEO (PEXELS + FALLBACK)
# =====================================================
class StockVideoRequest(BaseModel):
    query: str
    fallback_queries: list[str] | None = None
    duration: int = 30
    orientation: str = "vertical"
    platform: str = "youtube_shorts"

@app.post("/get-stock-video")
async def get_stock_video(req: StockVideoRequest):
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}

    queries = [req.query] + (req.fallback_queries or [])

    for q in queries:
        url = (
            "https://api.pexels.com/videos/search"
            f"?query={q}&orientation=portrait&per_page=1"
        )
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            continue

        data = res.json()
        if not data.get("videos"):
            continue

        video_url = data["videos"][0]["video_files"][0]["link"]
        return {"video_url": video_url}

    return {"video_url": None}

# =====================================================
# 4. RENDER VIDEO (FFMPEG SHORTS)
# =====================================================
class RenderRequest(BaseModel):
    video_url: str
    audio_url: str
    subtitle_text: str
    duration: int
    orientation: str = "vertical"
    resolution: str = "1080x1920"

@app.post("/render-video")
async def render_video(req: RenderRequest):
    video_path = VIDEO_DIR / f"{uuid.uuid4()}.mp4"
    audio_path = AUDIO_DIR / f"{uuid.uuid4()}.mp3"
    output_path = VIDEO_DIR / f"{uuid.uuid4()}.mp4"

    open(video_path, "wb").write(requests.get(req.video_url).content)
    open(audio_path, "wb").write(requests.get(req.audio_url).content)

    presets = [
        {"zoom": "0.0006", "contrast": "1.03", "noise": "6"},
        {"zoom": "0.0010", "contrast": "1.07", "noise": "10"},
        {"zoom": "0.0014", "contrast": "1.1", "noise": "14"},
    ]
    p = random.choice(presets)

    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"zoompan=z='min(zoom+{p['zoom']},1.05)':"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920,"
        f"eq=contrast={p['contrast']}:saturation=1.05:brightness=0.02,"
        f"noise=alls={p['noise']}:allf=t,"
        "vignette=PI/4,"
        f"drawtext=text='{req.subtitle_text}':"
        "fontcolor=white:fontsize=64:line_spacing=10:"
        "borderw=3:bordercolor=black:"
        "x=(w-text_w)/2:y=h*0.72"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-vf", vf,
        "-af", "highpass=f=120,lowpass=f=12000,volume=1.2",
        str(output_path),
    ]

    subprocess.run(cmd, check=True)

    return {
        "rendered_video_url": f"https://{PUBLIC_DOMAIN}/video/{output_path.name}"
    }

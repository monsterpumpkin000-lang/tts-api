from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uuid
import os
import subprocess
import requests
import random
import edge_tts

app = FastAPI()

TMP_DIR = "/tmp"
os.makedirs(TMP_DIR, exist_ok=True)

# =====================================================
# UTILS
# =====================================================

def ffmpeg_escape(text: str) -> str:
    """Escape text agar aman untuk ffmpeg drawtext"""
    return (
        text.replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace("\n", " ")
    )

def download_file(url: str, path: str):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)

# =====================================================
# 1. SCRIPT GENERATOR (OPTIONAL)
# =====================================================

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

# =====================================================
# 2. TEXT TO SPEECH (EDGE TTS)
# =====================================================

class TTSRequest(BaseModel):
    text: str

@app.post("/tts")
async def tts(req: TTSRequest):
    audio_id = f"{uuid.uuid4()}.mp3"
    audio_path = os.path.join(TMP_DIR, audio_id)

    communicate = edge_tts.Communicate(
        text=req.text,
        voice="en-US-JennyNeural",
        rate="+10%",
        pitch="+0Hz"
    )
    await communicate.save(audio_path)

    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename="voice.mp3"
    )

# =====================================================
# 3. GET STOCK VIDEO (PEXELS)
# =====================================================

class StockVideoRequest(BaseModel):
    query: str

@app.post("/get-stock-video")
async def get_stock_video(req: StockVideoRequest):
    headers = {
        "Authorization": os.getenv("PEXELS_API_KEY")
    }

    url = (
        "https://api.pexels.com/videos/search"
        f"?query={req.query}&orientation=portrait&per_page=1"
    )

    res = requests.get(url, headers=headers, timeout=20)
    res.raise_for_status()
    data = res.json()

    video_url = data["videos"][0]["video_files"][0]["link"]

    return {"video_url": video_url}

# =====================================================
# 4. RENDER VIDEO (FINAL, STABIL)
# =====================================================

class RenderRequest(BaseModel):
    video_url: str
    audio_url: str
    subtitle_text: str

@app.post("/render-video")
async def render_video(req: RenderRequest):
    video_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.mp4")
    audio_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.mp3")
    output_path = os.path.join(TMP_DIR, f"{uuid.uuid4()}.mp4")

    # download assets
    download_file(req.video_url, video_path)
    download_file(req.audio_url, audio_path)

    # escape subtitle text (INI KUNCI)
    subtitle = ffmpeg_escape(req.subtitle_text)

    # cinematic presets
    presets = [
        {"zoom": "0.0006", "contrast": "1.05", "noise": "6"},
        {"zoom": "0.0008", "contrast": "1.08", "noise": "10"},
        {"zoom": "0.0012", "contrast": "1.12", "noise": "14"},
    ]
    p = random.choice(presets)

    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"zoompan=z='min(zoom+{p['zoom']},1.06)':"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920,"
        f"eq=contrast={p['contrast']}:saturation=1.15:brightness=0.03,"
        f"noise=alls={p['noise']}:allf=t,"
        "vignette=PI/4,"
        f"drawtext=text='{subtitle}':"
        "fontcolor=white:fontsize=64:"
        "borderw=3:bordercolor=black:"
        "x=(w-text_w)/2:y=h*0.72"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-vf", vf,
        "-af", "highpass=f=120,lowpass=f=12000,volume=1.2",
        output_path
    ]

    subprocess.run(cmd, check=True)

    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename="shorts.mp4"
    )

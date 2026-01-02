from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid, os, subprocess, requests
import edge_tts

app = FastAPI()

# =========================
# TTS
# =========================
class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-JennyNeural"
    rate: str = "+10%"
    pitch: str = "+0Hz"

@app.post("/tts")
async def tts(req: TTSRequest):
    audio_path = f"/tmp/{uuid.uuid4()}.mp3"

    communicate = edge_tts.Communicate(
        text=req.text,
        voice=req.voice,
        rate=req.rate,
        pitch=req.pitch
    )
    await communicate.save(audio_path)

    return FileResponse(audio_path, media_type="audio/mpeg", filename="voice.mp3")

# =========================
# SCRIPT GENERATOR
# =========================
class ScriptRequest(BaseModel):
    theme: str
    audience: str

@app.post("/generate-script")
async def generate_script(req: ScriptRequest):
    hook = "Small daily habits fuel the unshakeable confidence you crave."
    body = "Consistency builds confidence faster than motivation ever will."
    ending = "Start small. Stay consistent."

    return {
        "voiceOverText": f"{hook} {body} {ending}",
        "theme": req.theme
    }

# =========================
# PEXELS STOCK VIDEO
# =========================
class StockVideoRequest(BaseModel):
    query: str

@app.post("/get-stock-video")
async def get_stock_video(req: StockVideoRequest):
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    url = f"https://api.pexels.com/videos/search?query={req.query}&orientation=portrait&per_page=1"

    res = requests.get(url, headers=headers).json()
    video_url = res["videos"][0]["video_files"][0]["link"]

    return {"video_url": video_url}

# =========================
# RENDER VIDEO (FFMPEG)
# =========================
class RenderRequest(BaseModel):
    video_url: str
    audio_url: str

@app.post("/render-video")
async def render_video(req: RenderRequest):
    video_path = f"/tmp/{uuid.uuid4()}.mp4"
    audio_path = f"/tmp/{uuid.uuid4()}.mp3"
    output_path = f"/tmp/{uuid.uuid4()}.mp4"

    open(video_path, "wb").write(requests.get(req.video_url).content)
    open(audio_path, "wb").write(requests.get(req.audio_url).content)

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
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        output_path
    ]

    subprocess.run(cmd, check=True)

    return FileResponse(output_path, media_type="video/mp4", filename="shorts.mp4")

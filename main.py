from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid
import edge_tts
import subprocess
import os

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
    filename = f"/tmp/{uuid.uuid4()}.mp3"

    communicate = edge_tts.Communicate(
        text=req.text,
        voice=req.voice,
        rate=req.rate,
        pitch=req.pitch
    )

    await communicate.save(filename)

    return FileResponse(
        path=filename,
        media_type="audio/mpeg",
        filename="voice.mp3"
    )

# =========================
# SCRIPT GENERATOR
# =========================
class ScriptRequest(BaseModel):
    theme: str
    audience: str
    duration_sec: int = 30

@app.post("/generate-script")
async def generate_script(req: ScriptRequest):
    hook = "Small daily habits fuel the unshakeable confidence you crave."
    body = (
        "Consistent practice in everyday situations gradually strengthens "
        "confidence without pressure."
    )
    ending = "Small actions lead to bigger change."

    voice_over = f"{hook}\n\n{body}\n\n{ending}"

    return {
        "hook": hook,
        "body": body,
        "ending": ending,
        "voiceOverText": voice_over
    }

# =========================
# RENDER VIDEO (FFMPEG)
# =========================
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid, subprocess, requests, os

class RenderRequest(BaseModel):
    image_url: str
    audio_url: str

@app.post("/render-video")
async def render_video(req: RenderRequest):
    image_path = f"/tmp/{uuid.uuid4()}.jpg"
    audio_path = f"/tmp/{uuid.uuid4()}.mp3"
    output_path = f"/tmp/{uuid.uuid4()}.mp4"

    # download image
    img = requests.get(req.image_url)
    with open(image_path, "wb") as f:
        f.write(img.content)

    # download audio
    aud = requests.get(req.audio_url)
    with open(audio_path, "wb") as f:
        f.write(aud.content)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        output_path
    ]

    subprocess.run(cmd, check=True)

    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename="shorts.mp4"
    )

class ImageRequest(BaseModel):
    prompt: str

# ============================
# IMAGE GENERATOR (OPENAI)
# ============================

from openai import OpenAI
import base64

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.post("/generate-image")
async def generate_image(req: ImageRequest):
    result = client.images.generate(
        model="gpt-image-1",
        prompt=req.prompt,
        size="1080x1920"
    )

    image_base64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    filename = f"/tmp/{uuid.uuid4()}.png"
    with open(filename, "wb") as f:
        f.write(image_bytes)

    return FileResponse(
        path=filename,
        media_type="image/png",
        filename="background.png"
    )

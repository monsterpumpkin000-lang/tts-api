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
# VIDEO RENDER (FFmpeg)
# =========================
@app.post("/render-video")
async def render_video(
    image: UploadFile = File(...),
    audio: UploadFile = File(...)
):
    image_path = f"/tmp/{uuid.uuid4()}.png"
    audio_path = f"/tmp/{uuid.uuid4()}.mp3"
    output_path = f"/tmp/{uuid.uuid4()}.mp4"

    try:
        with open(image_path, "wb") as f:
            f.write(await image.read())

        with open(audio_path, "wb") as f:
            f.write(await audio.read())

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

    finally:
        # cleanup (SUPER IMPORTANT)
        for f in [image_path, audio_path]:
            if os.path.exists(f):
                os.remove(f)


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

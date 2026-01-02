from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid, subprocess, requests, random, os

app = FastAPI()

# =====================================================
# MODELS
# =====================================================

class SubtitleStyle(BaseModel):
    font: str = "Montserrat"
    size: int = 64
    color: str = "#FFFFFF"
    stroke: str = "#000000"
    stroke_width: int = 3
    position: str = "bottom"
    highlight_color: str | None = None

class Subtitles(BaseModel):
    style: SubtitleStyle

class Editing(BaseModel):
    cut_on_emphasis: bool = True
    zoom_on_emphasis: bool = True
    zoom_scale: float = 1.05
    fade_in: float = 0.3
    fade_out: float = 0.3

class RenderRequest(BaseModel):
    video_url: str
    audio_url: str
    subtitle_text: str

    resolution: str = "1080x1920"
    subtitles: Subtitles | None = None
    editing: Editing | None = None


# =====================================================
# RENDER VIDEO
# =====================================================

@app.post("/render-video")
async def render_video(req: RenderRequest):

    video_path = f"/tmp/{uuid.uuid4()}.mp4"
    audio_path = f"/tmp/{uuid.uuid4()}.mp3"
    output_path = f"/tmp/{uuid.uuid4()}.mp4"

    # Download assets
    open(video_path, "wb").write(requests.get(req.video_url, timeout=30).content)
    open(audio_path, "wb").write(requests.get(req.audio_url, timeout=30).content)

    # Cinematic presets
    presets = [
        {"zoom": "0.0006", "contrast": "1.03", "noise": "6"},
        {"zoom": "0.0009", "contrast": "1.06", "noise": "10"},
        {"zoom": "0.0012", "contrast": "1.1", "noise": "14"},
    ]
    p = random.choice(presets)

    style = req.subtitles.style if req.subtitles else SubtitleStyle()
    edit = req.editing if req.editing else Editing()

    y_pos = "h*0.72" if style.position == "bottom" else "h*0.15"

    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"zoompan=z='min(zoom+{p['zoom']},1.1)':"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920,"
        f"eq=contrast={p['contrast']}:saturation=1.05:brightness=0.02,"
        f"noise=alls={p['noise']}:allf=t,"
        "vignette=PI/4,"
        f"drawtext=text='{req.subtitle_text}':"
        f"fontcolor={style.color}:fontsize={style.size}:"
        f"borderw={style.stroke_width}:bordercolor={style.stroke}:"
        f"x=(w-text_w)/2:y={y_pos}"
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

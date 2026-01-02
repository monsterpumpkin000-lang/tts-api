from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid, os, subprocess, requests, random
import edge_tts

app = FastAPI()

# =====================================================
# 1. SCRIPT GENERATOR
# =====================================================
class ScriptRequest(BaseModel):
    theme: str
    audience: str

@app.post("/generate-script")
async def generate_script(req: ScriptRequest):
    hook = "Small daily habits build unshakable confidence."
    body = "Consistency beats motivation when motivation fades."
    ending = "Start today. Stay consistent."

    subtitle = f"{hook} {body}"

    return {
        "voice_text": f"{hook} {body} {ending}",
        "subtitle_text": subtitle,
        "video_query": "cinematic calm nature"
    }

# =====================================================
# 2. TEXT TO SPEECH (EDGE TTS)
# =====================================================
class TTSRequest(BaseModel):
    text: str

@app.post("/tts")
async def tts(req: TTSRequest):
    audio_path = f"/tmp/{uuid.uuid4()}.mp3"

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

    res = requests.get(url, headers=headers, timeout=15)
    res.raise_for_status()

    data = res.json()
    video_url = data["videos"][0]["video_files"][0]["link"]

    return {
        "video_url": video_url
    }

# =====================================================
# 4. RENDER VIDEO (FFMPEG + CINEMATIC + SUBTITLE)
# =====================================================
class RenderRequest(BaseModel):
    video_url: str
    audio_url: str
    subtitle_text: str

@app.post("/render-video")
async def render_video(req: RenderRequest):
    video_path = f"/tmp/{uuid.uuid4()}.mp4"
    audio_path = f"/tmp/{uuid.uuid4()}.mp3"
    output_path = f"/tmp/{uuid.uuid4()}.mp4"

    # download assets
    open(video_path, "wb").write(requests.get(req.video_url).content)
    open(audio_path, "wb").write(requests.get(req.audio_url).content)

    # random cinematic presets
    presets = [
        {"zoom": "0.0006", "contrast": "1.03", "noise": "6"},
        {"zoom": "0.0008", "contrast": "1.05", "noise": "10"},
        {"zoom": "0.0012", "contrast": "1.1", "noise": "14"},
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

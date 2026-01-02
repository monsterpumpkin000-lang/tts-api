from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uuid, os, subprocess, requests, random, math
import edge_tts

# =====================================================
# APP INIT
# =====================================================
app = FastAPI()

raw_base = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").rstrip("/")
if raw_base and not raw_base.startswith("http"):
    BASE_URL = f"https://{raw_base}"
else:
    BASE_URL = raw_base
AUDIO_DIR = "audio"
VIDEO_DIR = "output"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
app.mount("/output", StaticFiles(directory=VIDEO_DIR), name="output")

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

    return {
        "voice_text": f"{hook} {body} {ending}",
        "subtitle_text": f"{hook} {body}",
        "video_query": "cinematic calm nature"
    }

# =====================================================
# 2. TEXT TO SPEECH (RETURN URL, NOT BINARY)
# =====================================================
class TTSRequest(BaseModel):
    text: str

@app.post("/tts")
async def tts(req: TTSRequest):
    filename = f"{uuid.uuid4().hex}.mp3"
    path = os.path.join(AUDIO_DIR, filename)

    communicate = edge_tts.Communicate(
        text=req.text,
        voice="en-US-JennyNeural",
        rate="+10%",
        pitch="+0Hz"
    )
    await communicate.save(path)

    words = len(req.text.split())
    duration = max(3, math.ceil(words * 0.45))

    return {
        "audio_url": f"{BASE_URL}/audio/{filename}",
        "duration": duration
    }

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
# 4. RENDER VIDEO (ALL EDITING DONE HERE)
# =====================================================
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

    open(video_path, "wb").write(requests.get(req.video_url).content)
    open(audio_path, "wb").write(requests.get(req.audio_url).content)

    presets = [
        {"zoom": "0.0006", "contrast": "1.03", "noise": "6"},
        {"zoom": "0.0009", "contrast": "1.06", "noise": "10"},
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

    return {
        "video_url": f"{BASE_URL}/output/{output_file}"
    }

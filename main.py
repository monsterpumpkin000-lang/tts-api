from fastapi import FastAPI
from pydantic import BaseModel
import uuid
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
    filename = f"{uuid.uuid4()}.mp3"

    communicate = edge_tts.Communicate(
        text=req.text,
        voice=req.voice,
        rate=req.rate,
        pitch=req.pitch
    )

    await communicate.save(filename)
    return {"file": filename}


# =========================
# SCRIPT GENERATOR
# =========================
class ScriptRequest(BaseModel):
    theme: str
    audience: str
    duration_sec: int = 30

@app.post("/generate-script")
async def generate_script(req: ScriptRequest):
    # NANTI GANTI OPENAI / GPT
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

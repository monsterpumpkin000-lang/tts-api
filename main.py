from fastapi import FastAPI
from pydantic import BaseModel
import edge_tts
import uuid

app = FastAPI()

class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-GuyNeural"
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


from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ScriptRequest(BaseModel):
    theme: str
    audience: str
    duration_sec: int = 30

@app.post("/generate-script")
async def generate_script(req: ScriptRequest):
    # ⬇️ nanti ini bisa kamu ganti OpenAI API
    hook = f"Small daily habits fuel the unshakeable confidence you crave."
    body = f"Consistent practice in everyday situations gradually strengthens confidence without pressure."
    ending = f"Small actions lead to bigger change."

    voice_over = f"{hook}\n\n{body}\n\n{ending}"

    return {
        "hook": hook,
        "body": body,
        "ending": ending,
        "voiceOverText": voice_over
    }

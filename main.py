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

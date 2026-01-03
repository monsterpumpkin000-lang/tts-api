FROM python:3.11-slim

# System deps
RUN apt-get update \
 && apt-get install -y ffmpeg \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# ⚠️ WAJIB pakai shell biar ${PORT} ke-expand
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port $PORT"

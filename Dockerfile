FROM python:3.11-slim

# Install system dependencies (FFMPEG)
RUN apt-get update \
    && apt-get install -y ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# PENTING: pakai shell supaya $PORT terbaca
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]

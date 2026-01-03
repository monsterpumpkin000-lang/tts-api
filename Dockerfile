FROM python:3.11-slim

# system deps
RUN apt-get update \
 && apt-get install -y ffmpeg \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# IMPORTANT: JANGAN sh -c, JANGAN ${PORT} DI DOCKER
CMD ["python", "main.py"]

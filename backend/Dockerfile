FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime

WORKDIR /app

# Systempaket: ffmpeg krävs för ljudkonvertering
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python-beroenden
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Skapa lagringskataloger
RUN mkdir -p /app/storage/uploads /app/storage/models_cache /app/storage/db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Setup-guide

## Förutsättningar

| Krav | Minimum | Rekommenderat |
|------|---------|---------------|
| OS | Windows 10/11 | Windows 11 |
| RAM | 8 GB | 16 GB |
| GPU VRAM | 4 GB (kb-whisper-small) | 8 GB (kb-whisper-medium) |
| Disk | 10 GB | 20 GB |
| CUDA | 11.8+ | 12.8 |
| Docker | Docker Desktop 4.x | Latest |

---

## 1. GPU-setup för Docker på Windows

### 1.1 Aktivera WSL2

```powershell
wsl --install
wsl --set-default-version 2
```

Starta om datorn.

### 1.2 Installera NVIDIA Container Toolkit

Kör i WSL2-terminalen:

```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 1.3 Verifiera GPU i Docker

```bash
docker run --rm --gpus all nvidia/cuda:12.8-base-ubuntu22.04 nvidia-smi
```

---

## 2. HuggingFace-token (för diarization)

Om `DIARIZATION_ENABLED=true` i `.env`:

1. Skapa konto på [huggingface.co](https://huggingface.co)
2. Gå till [Settings → Access Tokens](https://huggingface.co/settings/tokens) och skapa en token
3. Acceptera villkoren för [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
4. Acceptera villkoren för [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
5. Lägg till token i `.env`:
   ```
   HF_TOKEN=hf_xxx...
   DIARIZATION_ENABLED=true
   ```

**Utan diarization** fungerar transkribering normalt men utan talarindelning.

---

## 3. Lokal körning utan Docker

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Kopiera och konfigurera `.env`:
```bash
cp ../.env.example .env
# Redigera .env: sätt STORAGE_DIR, DATABASE_URL till lokala sökvägar
```

Starta:
```bash
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

---

## 4. Modellcache

Modeller laddas ner automatiskt vid första körning till `MODELS_CACHE_DIR`.
- `kb-whisper-small`: ~300 MB
- `kb-whisper-medium`: ~1.5 GB
- `kb-whisper-large`: ~3 GB
- wav2vec2-large-voxrex-swedish: ~1.2 GB
- pyannote/speaker-diarization-3.1: ~400 MB

Använd volym-mount i Docker för att bevara cachen mellan omstarter:
```yaml
volumes:
  - transcriber_models:/app/storage/models_cache
```

---

## 5. Modellbyte

Byt modell i `.env`:
```
TRANSCRIPTION_MODEL=KBLab/kb-whisper-medium
```

Tillgängliga storlekar:
- `KBLab/kb-whisper-tiny` – snabbast, lägst kvalitet
- `KBLab/kb-whisper-base`
- `KBLab/kb-whisper-small` (**rekommenderat för MVP**, slår OpenAI large-v3)
- `KBLab/kb-whisper-medium`
- `KBLab/kb-whisper-large` – bäst kvalitet, kräver mer VRAM

---

## 6. Fallback utan GPU

Systemet fungerar på CPU men är avsevärt långsammare.
Sätt i `docker-compose.yml`:
```yaml
# Kommentera bort deploy.resources.reservations för CPU-körning
```

Med `kb-whisper-small` på CPU: ~10–30× realtid (1h möte = 10–30h transkribering).

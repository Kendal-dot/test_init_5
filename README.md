# Lokal svensk mötestranskriberingsplattform

Privacy-first plattform för transkribering av svenska möten. All bearbetning sker lokalt – inga molntjänster används.

**Teknikstack:**
- **Transkribering:** [KB-Whisper](https://huggingface.co/collections/KBLab/kb-whisper-67af9eafb24da903b63cc4aa) via [easytranscriber](https://github.com/kb-labb/easytranscriber)
- **Talarindelning:** pyannote.audio
- **Backend:** Python + FastAPI + SQLAlchemy + SQLite
- **Frontend:** React + Vite + JavaScript
- **Körning:** Docker + NVIDIA GPU

---

## Snabbstart

### Förutsättningar

- Docker Desktop (med WSL2 på Windows)
- NVIDIA GPU + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- Git

### 1. Klona och konfigurera

```bash
git clone <repo-url>
cd <repo>
cp .env.example .env
```

Redigera `.env` och ange åtminstone:
- `HF_TOKEN` om du vill använda pyannote-diarization (se [setup.md](docs/setup.md))

### 2. Starta med Docker

```bash
cd infra
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API-dokumentation: http://localhost:8000/docs

### 3. Lokal utveckling (utan Docker)

**Backend:**
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Frontend körs på http://localhost:5173 och proxar API-anrop till backend på port 8000.

---

## Funktioner (MVP)

- **Filuppladdning** – Ladda upp ljud- och videofiler (MP3, WAV, MP4, M4A, etc.)
- **Automatisk transkribering** – KB-Whisper optimerad för svenska
- **Talarindelning** – Talare 1, Talare 2, etc. via pyannote.audio
- **Jobbstatus** – Realtidsuppdatering av transkriberingsstatus
- **Redigerbar transkriptvy** – Redigera och spara ändringar direkt i UI
- **Fulltextsök** – Sök i alla transkript
- **JSON-export** – Exportera transkript med tidsmarkeringar och talardata
- **Live-transkribering** – Chunk-baserad realtidsövervak av pågående möten

---

## Arkitektur

Se [docs/architecture.md](docs/architecture.md) för detaljerad beskrivning.

## Pipeline

Se [docs/pipeline.md](docs/pipeline.md) för hur KB-Whisper och easytranscriber används.

## Docker och GPU

Se [docs/setup.md](docs/setup.md) för GPU-setup och Docker-konfiguration.

---

## Kända begränsningar (MVP)

- Live-transkribering är chunk-baserad (10s chunks), inte äkta realtid
- Talarnamn ges automatiskt som "Talare 1", "Talare 2" etc. – ingen manuell namngivning i MVP
- Diarization kräver HuggingFace-token och godkännande av pyannote-villkor
- SQLite används (Postgres kan konfigureras senare via `DATABASE_URL`)

## TODO / Nästa steg

- [ ] Alembic-migrationer för databasschema
- [ ] Manuell namngivning av talare
- [ ] Bättre realtids-live-transkribering med VAD
- [ ] Postgres-stöd
- [ ] Celery + Redis för skalbar jobbhantering
- [ ] Autentisering
- [ ] AI-sammanfattning av möten

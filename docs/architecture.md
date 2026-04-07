# Arkitektur

## Systemöversikt

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                            │
│                                                             │
│  ┌──────────────────┐         ┌──────────────────────────┐  │
│  │   Frontend       │         │   Backend                 │  │
│  │   React + Vite   │◄──────►│   FastAPI + SQLAlchemy    │  │
│  │   Port: 3000     │  HTTP   │   Port: 8000              │  │
│  │                  │  WS     │                           │  │
│  └──────────────────┘         │  ┌──────────────────────┐│  │
│                               │  │  Job Queue (asyncio)  ││  │
│                               │  └──────────┬───────────┘│  │
│                               │             │             │  │
│                               │  ┌──────────▼───────────┐│  │
│                               │  │  Pipeline Adapter     ││  │
│                               │  │  KB-Whisper +        ││  │
│                               │  │  easytranscriber     ││  │
│                               │  │  pyannote.audio      ││  │
│                               │  └──────────┬───────────┘│  │
│                               └─────────────┼─────────────┘  │
│                                             │                 │
│  ┌──────────────────────────────────────────▼─────────────┐  │
│  │                  Docker Volumes                         │  │
│  │  transcriber_storage: /app/storage/                     │  │
│  │    ├── uploads/          (originalfiler)                │  │
│  │    ├── db/               (SQLite)                       │  │
│  │    └── models_cache/     (ML-modeller)                  │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Backend-lager

```
app/
├── main.py              # FastAPI-app, startup/shutdown
├── core/
│   ├── config.py        # Pydantic-settings (env → config)
│   └── logging.py       # Logging-setup
├── api/routes/
│   ├── upload.py        # POST /api/upload
│   ├── jobs.py          # GET /api/jobs, /api/jobs/{id}
│   ├── transcripts.py   # GET /api/transcripts/{id}, PATCH /segments/{id}
│   ├── search.py        # GET /api/search?q=...
│   └── live.py          # WS /ws/live/transcribe
├── db/
│   ├── base.py          # SQLAlchemy engine + session + Base
│   ├── models/          # ORM-modeller (Meeting, Transcript, Segment)
│   └── repositories/    # Repository-pattern (MeetingRepo, etc.)
├── services/
│   ├── job_service.py       # Uppladdning + jobbschemaläggning
│   ├── transcript_service.py # Spara + exportera transkript
│   └── search_service.py    # Sök i transkript
├── pipeline/
│   ├── interface.py          # Abstrakt TranscriptionPipeline
│   ├── easytranscriber_adapter.py
│   ├── live_adapter.py
│   ├── diarization.py
│   └── audio_utils.py
└── workers/
    └── job_worker.py     # asyncio-baserad jobbkö
```

## Lagringsabstraktion

Repository-mönstret abstraherar bort databasdetaljer:
- `BaseRepository[T]` – generisk CRUD
- `MeetingRepository`, `TranscriptRepository`, `SegmentRepository` – specifik logik

Byte till Postgres: ändra `DATABASE_URL` i `.env`:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
```
SQLAlchemy hanterar resten.

## Pipeline-abstraktion

`TranscriptionPipeline` (interface.py) definierar kontraktet:
```python
class TranscriptionPipeline(ABC):
    async def transcribe(self, file_path: str) -> TranscriptionResult: ...
    def is_available(self) -> bool: ...
```

`EasytranscriberAdapter` implementerar interfacet.
Nytt backend: implementera interfacet, byt adapter i `job_service.py`.

## Jobbkö

`JobQueue` (workers/job_worker.py):
- asyncio-baserad in-process kö
- Semaphore begränsar parallella jobb (default: 1 för GPU)
- Stateless-design: byte till Celery kräver bara ny `enqueue`-implementation

## Datamodell

```
Meeting (1) ──── (1) Transcript (1) ──── (N) Segment
  id                  id                   id
  status              meeting_id           transcript_id
  source_type         created_at           start_time
  original_filename   updated_at           end_time
  file_path                                speaker_label
  duration                                 text
  model_used                               original_text
  error_message                            is_edited
```

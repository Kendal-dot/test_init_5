from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.base import init_db
from app.workers.job_worker import get_job_queue

settings = get_settings()
setup_logging(debug=settings.debug)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup och shutdown av app-resurser."""
    logger.info("Startar mötestranskriberingstjänsten...")
    settings.ensure_dirs()
    await init_db()

    queue = get_job_queue()
    queue.start()

    # Förladda KB-Whisper i bakgrunden så att live-transkribering svarar direkt
    # vid första anslutningen (istället för att ta 20-30s på första chunken)
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _preload_live_model)

    logger.info("Tjänsten redo – modell laddas i bakgrunden")

    yield

    logger.info("Stänger ner tjänsten...")
    await queue.stop()


def _preload_live_model():
    try:
        from app.pipeline.live_adapter import preload_model
        preload_model()
    except Exception as exc:
        logger.warning(f"Kunde inte förladdda live-modell: {exc}")


app = FastAPI(
    title="Svensk Mötestranskriberare",
    description="Lokal, privacy-first transkribering av svenska möten med KB-Whisper.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
from app.api.routes import upload, jobs, transcripts, search, live, speakers  # noqa: E402

app.include_router(upload.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(transcripts.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(speakers.router, prefix="/api")
app.include_router(live.router, prefix="/ws")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "transcriber"}

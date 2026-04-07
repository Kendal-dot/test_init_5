"""
Jobbservice – orkestrerar uppladdning, köhantering och statushållning.
Pipeline-köret delegeras till pipeline-adaptern via ett abstrakt interface.
"""

import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import AsyncSessionLocal
from app.db.models.meeting import Meeting
from app.db.repositories import MeetingRepository
from app.workers.job_worker import Job, get_job_queue

logger = get_logger(__name__)
settings = get_settings()

ALLOWED_EXTENSIONS = {
    ".mp3", ".mp4", ".wav", ".m4a", ".ogg", ".flac",
    ".webm", ".mkv", ".mov", ".aac", ".wma",
}


async def create_upload_job(file: UploadFile) -> Meeting:
    """Spara uppladdad fil och skapa ett transkriberingsjobb i kön."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Filtypen '{suffix}' stöds inte. Tillåtna: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    stored_name = f"{uuid.uuid4()}{suffix}"
    file_path = Path(settings.uploads_dir) / stored_name

    # Skriv fil till disk
    contents = await file.read()
    file_path.write_bytes(contents)
    file_size = len(contents)
    logger.info(f"Fil sparad: {file_path} ({file_size} bytes)")

    async with AsyncSessionLocal() as session:
        repo = MeetingRepository(session)
        meeting = Meeting(
            original_filename=file.filename,
            stored_filename=stored_name,
            file_path=str(file_path),
            file_size_bytes=file_size,
            status="queued",
            source_type="upload",
        )
        meeting = await repo.create(meeting)
        await session.commit()
        meeting_id = meeting.id

    # Schemalägg transkribering
    queue = get_job_queue()
    job = Job(
        meeting_id=meeting_id,
        fn=_run_transcription_job,
        args=(meeting_id,),
    )
    await queue.enqueue(job)
    logger.info(f"Transkriberingsjobb skapat: meeting_id={meeting_id}")

    # Hämta färskt objekt att returnera
    async with AsyncSessionLocal() as session:
        repo = MeetingRepository(session)
        return await repo.get(meeting_id)


async def _run_transcription_job(meeting_id: str) -> None:
    """Körs av jobbarbetaren. Hämtar pipeline-adapter och kör transkribering."""
    from app.pipeline.easytranscriber_adapter import EasytranscriberAdapter
    from app.services.transcript_service import save_transcription_result

    async with AsyncSessionLocal() as session:
        repo = MeetingRepository(session)
        meeting = await repo.get(meeting_id)
        if not meeting:
            logger.error(f"Möte hittades inte: {meeting_id}")
            return
        await repo.update_status(meeting_id, "processing")
        await session.commit()
        file_path = meeting.file_path

    try:
        adapter = EasytranscriberAdapter()
        result = await adapter.transcribe(file_path)

        async with AsyncSessionLocal() as session:
            await save_transcription_result(session, meeting_id, result)
            await session.commit()

    except Exception as exc:
        logger.exception(f"Transkribering misslyckades för {meeting_id}: {exc}")
        async with AsyncSessionLocal() as session:
            repo = MeetingRepository(session)
            await repo.update_status(meeting_id, "failed", error_message=str(exc))
            await session.commit()

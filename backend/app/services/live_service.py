"""
Sparar en live-transkriberingssession till databasen.
Skapar Meeting (source_type='live') + Transcript + Segments,
precis som pipeline-resultatet för uppladdade filer.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.meeting import Meeting
from app.db.models.segment import Segment
from app.db.models.transcript import Transcript
from app.db.repositories import MeetingRepository, SegmentRepository, TranscriptRepository
from app.schemas.live import SaveLiveSessionRequest

logger = get_logger(__name__)


async def save_live_session(
    session: AsyncSession,
    body: SaveLiveSessionRequest,
) -> Meeting:
    """
    Sparar en live-session som ett komplett möte i databasen.
    Returnerar det skapade Meeting-objektet (med id för navigering).
    """
    meeting_repo = MeetingRepository(session)
    transcript_repo = TranscriptRepository(session)
    segment_repo = SegmentRepository(session)

    # Räkna ut total duration från segmentens tider
    duration = (
        max(s.end for s in body.segments) if body.segments else 0.0
    )

    # Generera ett filnamn från titel eller tidsstämpel
    now = datetime.now(timezone.utc)
    display_name = body.title or f"Live-möte {now.strftime('%Y-%m-%d %H:%M')}"

    meeting = Meeting(
        original_filename=display_name,
        stored_filename=f"live_{uuid.uuid4().hex[:8]}",
        file_path="",               # Ingen fil – live-session
        file_size_bytes=None,
        status="completed",
        source_type="live",
        language="sv",
        duration=duration,
        model_used="KBLab/kb-whisper-small",
        pipeline_used="live-keyword-v1",
    )
    meeting = await meeting_repo.create(meeting)

    transcript = Transcript(meeting_id=meeting.id)
    transcript = await transcript_repo.create(transcript)

    segments = [
        Segment(
            transcript_id=transcript.id,
            start_time=seg.start,
            end_time=seg.end,
            speaker_label=seg.speaker,
            text=seg.text,
            original_text=seg.text,
            is_edited=False,
        )
        for seg in body.segments
    ]
    await segment_repo.bulk_create(segments)

    logger.info(
        f"Live-session sparad: meeting_id={meeting.id}, "
        f"{len(segments)} segment, {duration:.0f}s"
    )

    # Generera TXT + JSON-export automatiskt
    try:
        from app.services.transcript_service import save_export_files
        save_export_files(
            meeting_id=meeting.id,
            filename=display_name,
            duration=duration,
            source_type="live",
            created_at=now,
            model_used="KBLab/kb-whisper-small",
            segments=[
                {"start": s.start, "end": s.end, "speaker": s.speaker, "text": s.text}
                for s in body.segments
            ],
        )
    except Exception as exc:
        logger.warning(f"Kunde inte skapa exportfiler för live-session: {exc}")

    return meeting

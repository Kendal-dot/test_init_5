"""
Transkriptservice – sparar pipeline-resultat och hanterar redigering/export.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.segment import Segment
from app.db.models.transcript import Transcript
from app.db.repositories import MeetingRepository, SegmentRepository, TranscriptRepository
from app.pipeline.interface import TranscriptionResult
from app.schemas.transcript import TranscriptExport

logger = get_logger(__name__)
settings = get_settings()


async def save_transcription_result(
    session: AsyncSession,
    meeting_id: str,
    result: TranscriptionResult,
) -> Transcript:
    """Spara ett TranscriptionResult till databasen."""
    meeting_repo = MeetingRepository(session)
    transcript_repo = TranscriptRepository(session)
    segment_repo = SegmentRepository(session)

    # Uppdatera mötesstatus och metadata
    await meeting_repo.update_after_transcription(
        meeting_id,
        duration=result.duration,
        model_used=result.model_used,
        pipeline_used=result.pipeline_used,
    )

    # Skapa eller uppdatera transkriptobjektet
    existing = await transcript_repo.get_by_meeting_id(meeting_id)
    if existing:
        transcript = existing
    else:
        transcript = Transcript(meeting_id=meeting_id)
        transcript = await transcript_repo.create(transcript)

    # Spara segment
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
        for seg in result.segments
    ]
    await segment_repo.bulk_create(segments)
    logger.info(
        f"Sparade {len(segments)} segment för meeting_id={meeting_id}"
    )
    return transcript


async def update_segment_text(
    session: AsyncSession, segment_id: int, new_text: str
) -> Segment | None:
    repo = SegmentRepository(session)
    return await repo.update_text(segment_id, new_text)


async def get_transcript_export(
    session: AsyncSession, meeting_id: str
) -> TranscriptExport | None:
    meeting_repo = MeetingRepository(session)
    transcript_repo = TranscriptRepository(session)

    meeting = await meeting_repo.get(meeting_id)
    if not meeting:
        return None

    transcript = await transcript_repo.get_by_meeting_id(meeting_id)
    if not transcript:
        return None

    transcript_with_segs = await transcript_repo.get_with_segments(transcript.id)

    return TranscriptExport(
        meeting_id=meeting_id,
        filename=meeting.original_filename,
        language=meeting.language,
        duration=meeting.duration,
        source_type=meeting.source_type,
        created_at=meeting.created_at,
        model=meeting.model_used,
        pipeline=meeting.pipeline_used,
        segments=[
            {
                "id": seg.id,
                "start": seg.start_time,
                "end": seg.end_time,
                "speaker": seg.speaker_label,
                "text": seg.text,
                "is_edited": seg.is_edited,
            }
            for seg in transcript_with_segs.segments
        ],
    )

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import get_db
from app.db.repositories import MeetingRepository, SegmentRepository, TranscriptRepository
from app.schemas.segment import SegmentResponse, SegmentUpdate
from app.schemas.transcript import TranscriptResponse
from app.services.transcript_service import (
    get_transcript_export,
    save_export_files,
    update_segment_text,
)

settings = get_settings()

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


@router.get("/{meeting_id}", response_model=TranscriptResponse)
async def get_transcript(meeting_id: str, session: AsyncSession = Depends(get_db)):
    """Hämta transkript med alla segment för ett möte."""
    repo = TranscriptRepository(session)
    transcript = await repo.get_by_meeting_id(meeting_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transkript hittades inte")
    return transcript


@router.patch("/segments/{segment_id}", response_model=SegmentResponse)
async def update_segment(
    segment_id: int,
    body: SegmentUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Uppdatera texten i ett specifikt segment (redigering)."""
    segment = await update_segment_text(session, segment_id, body.text)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment hittades inte")
    return segment


@router.patch("/segments/{segment_id}/restore", response_model=SegmentResponse)
async def restore_segment(segment_id: int, session: AsyncSession = Depends(get_db)):
    """Återställ ett segment till original-texten."""
    repo = SegmentRepository(session)
    segment = await repo.get(segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment hittades inte")
    segment.text = segment.original_text
    segment.is_edited = False
    await session.flush()
    return segment


@router.get("/{meeting_id}/export")
async def export_transcript(meeting_id: str, session: AsyncSession = Depends(get_db)):
    """Exportera transkript som JSON."""
    export = await get_transcript_export(session, meeting_id)
    if not export:
        raise HTTPException(status_code=404, detail="Transkript hittades inte")
    return JSONResponse(
        content=export.model_dump(mode="json"),
        headers={
            "Content-Disposition": f'attachment; filename="transcript_{meeting_id}.json"'
        },
    )


async def _ensure_export_files(meeting_id: str, session: AsyncSession) -> None:
    """Generera exportfiler on-the-fly om de saknas (för äldre möten)."""
    exports_dir = Path(settings.resolved_exports_dir)
    txt_exists = (exports_dir / f"transcript_{meeting_id}.txt").exists()
    json_exists = (exports_dir / f"transcript_{meeting_id}.json").exists()

    if txt_exists and json_exists:
        return

    meeting_repo = MeetingRepository(session)
    transcript_repo = TranscriptRepository(session)

    meeting = await meeting_repo.get(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Möte hittades inte")

    transcript = await transcript_repo.get_by_meeting_id(meeting_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transkript hittades inte")

    transcript_with_segs = await transcript_repo.get_with_segments(transcript.id)

    save_export_files(
        meeting_id=meeting_id,
        filename=meeting.original_filename,
        duration=meeting.duration,
        source_type=meeting.source_type,
        created_at=meeting.created_at,
        model_used=meeting.model_used,
        segments=[
            {
                "start": seg.start_time,
                "end": seg.end_time,
                "speaker": seg.speaker_label,
                "text": seg.text,
            }
            for seg in transcript_with_segs.segments
        ],
    )


@router.get("/{meeting_id}/export/txt")
async def export_transcript_txt(meeting_id: str, session: AsyncSession = Depends(get_db)):
    """Exportera transkript som TXT – rent textformat för vektordatabas-indexering."""
    await _ensure_export_files(meeting_id, session)
    txt_path = Path(settings.resolved_exports_dir) / f"transcript_{meeting_id}.txt"
    return FileResponse(
        path=str(txt_path),
        filename=f"transcript_{meeting_id}.txt",
        media_type="text/plain; charset=utf-8",
    )


@router.get("/{meeting_id}/export/json")
async def export_transcript_json_file(meeting_id: str, session: AsyncSession = Depends(get_db)):
    """Exportera transkript som JSON – strukturerat format för vektordatabas-indexering."""
    await _ensure_export_files(meeting_id, session)
    json_path = Path(settings.resolved_exports_dir) / f"transcript_{meeting_id}.json"
    return FileResponse(
        path=str(json_path),
        filename=f"transcript_{meeting_id}.json",
        media_type="application/json; charset=utf-8",
    )

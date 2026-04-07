from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.repositories import SegmentRepository, TranscriptRepository
from app.schemas.segment import SegmentResponse, SegmentUpdate
from app.schemas.transcript import TranscriptResponse
from app.services.transcript_service import get_transcript_export, update_segment_text

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

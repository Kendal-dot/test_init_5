from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.repositories import MeetingRepository
from app.schemas.meeting import MeetingListResponse, MeetingResponse
from app.workers.job_worker import get_job_queue

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=MeetingListResponse)
async def list_jobs(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """Lista alla transkriberingsjobb, nyast först."""
    repo = MeetingRepository(session)
    items = await repo.list_with_transcript(limit=limit, offset=offset)
    total = await repo.count()
    return MeetingListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_job(meeting_id: str, session: AsyncSession = Depends(get_db)):
    """Hämta status och metadata för ett specifikt jobb."""
    repo = MeetingRepository(session)
    meeting = await repo.get(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Jobb hittades inte")
    return meeting


@router.get("/queue/status")
async def queue_status():
    """Returnerar aktuell kö-längd."""
    queue = get_job_queue()
    return {"queue_size": queue.queue_size()}

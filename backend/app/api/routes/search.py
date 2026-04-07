from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.schemas.segment import SegmentSearchResult
from app.services.search_service import search_transcripts

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SegmentSearchResult])
async def search(
    q: str = Query(..., min_length=2, description="Sökterm"),
    limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_db),
):
    """Sök i alla transkript. Returnerar matchande segment med meeting_id."""
    return await search_transcripts(session, q, limit=limit)

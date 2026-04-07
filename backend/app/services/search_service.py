"""
Söktjänst – enkel LIKE-sökning i alla transkript.
Designad för att kunna ersättas med FTS (SQLite FTS5 eller Elasticsearch) senare.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.segment import Segment
from app.db.models.transcript import Transcript
from app.schemas.segment import SegmentSearchResult


async def search_transcripts(
    session: AsyncSession, query: str, limit: int = 100
) -> list[SegmentSearchResult]:
    """Sök i all segmenttext. Returnerar segment med tillhörande meeting_id."""
    if not query or len(query.strip()) < 2:
        return []

    result = await session.execute(
        select(Segment, Transcript.meeting_id)
        .join(Transcript, Segment.transcript_id == Transcript.id)
        .where(Segment.text.ilike(f"%{query.strip()}%"))
        .order_by(Segment.start_time)
        .limit(limit)
    )

    rows = result.all()
    return [
        SegmentSearchResult(
            id=seg.id,
            transcript_id=seg.transcript_id,
            meeting_id=meeting_id,
            start_time=seg.start_time,
            end_time=seg.end_time,
            speaker_label=seg.speaker_label,
            text=seg.text,
        )
        for seg, meeting_id in rows
    ]

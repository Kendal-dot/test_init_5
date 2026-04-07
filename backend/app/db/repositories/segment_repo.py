from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.segment import Segment
from app.db.repositories.base import BaseRepository


class SegmentRepository(BaseRepository[Segment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Segment, session)

    async def get_by_transcript(self, transcript_id: int) -> list[Segment]:
        result = await self.session.execute(
            select(Segment)
            .where(Segment.transcript_id == transcript_id)
            .order_by(Segment.start_time)
        )
        return list(result.scalars().all())

    async def bulk_create(self, segments: list[Segment]) -> list[Segment]:
        for seg in segments:
            self.session.add(seg)
        await self.session.flush()
        return segments

    async def update_text(self, segment_id: int, text: str) -> Segment | None:
        segment = await self.get(segment_id)
        if segment:
            segment.text = text
            segment.is_edited = True
            await self.session.flush()
        return segment

    async def search_in_transcript(
        self, transcript_id: int, query: str
    ) -> list[Segment]:
        """Enkel LIKE-baserad sökning. Kan ersättas med FTS senare."""
        result = await self.session.execute(
            select(Segment)
            .where(
                Segment.transcript_id == transcript_id,
                Segment.text.ilike(f"%{query}%"),
            )
            .order_by(Segment.start_time)
        )
        return list(result.scalars().all())

    async def search_global(self, query: str, limit: int = 100) -> list[Segment]:
        """Sök i alla transkript. Returnerar segment med transcript_id för vidare hämtning."""
        result = await self.session.execute(
            select(Segment)
            .where(Segment.text.ilike(f"%{query}%"))
            .order_by(Segment.start_time)
            .limit(limit)
        )
        return list(result.scalars().all())

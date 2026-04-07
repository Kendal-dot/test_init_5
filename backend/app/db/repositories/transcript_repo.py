from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.transcript import Transcript
from app.db.repositories.base import BaseRepository


class TranscriptRepository(BaseRepository[Transcript]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Transcript, session)

    async def get_by_meeting_id(self, meeting_id: str) -> Transcript | None:
        result = await self.session.execute(
            select(Transcript)
            .options(selectinload(Transcript.segments))
            .where(Transcript.meeting_id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def get_with_segments(self, transcript_id: int) -> Transcript | None:
        result = await self.session.execute(
            select(Transcript)
            .options(selectinload(Transcript.segments))
            .where(Transcript.id == transcript_id)
        )
        return result.scalar_one_or_none()

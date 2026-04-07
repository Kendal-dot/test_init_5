from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.meeting import Meeting
from app.db.repositories.base import BaseRepository


class MeetingRepository(BaseRepository[Meeting]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Meeting, session)

    async def list_with_transcript(
        self, limit: int = 50, offset: int = 0
    ) -> list[Meeting]:
        result = await self.session.execute(
            select(Meeting)
            .options(selectinload(Meeting.transcript))
            .order_by(desc(Meeting.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_with_transcript(self, meeting_id: str) -> Meeting | None:
        result = await self.session.execute(
            select(Meeting)
            .options(selectinload(Meeting.transcript))
            .where(Meeting.id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, meeting_id: str, status: str, error_message: str | None = None
    ) -> Meeting | None:
        meeting = await self.get(meeting_id)
        if meeting:
            meeting.status = status
            if error_message is not None:
                meeting.error_message = error_message
            await self.session.flush()
        return meeting

    async def update_after_transcription(
        self,
        meeting_id: str,
        duration: float | None,
        model_used: str,
        pipeline_used: str,
    ) -> Meeting | None:
        meeting = await self.get(meeting_id)
        if meeting:
            meeting.duration = duration
            meeting.model_used = model_used
            meeting.pipeline_used = pipeline_used
            meeting.status = "completed"
            await self.session.flush()
        return meeting

    async def count(self) -> int:
        from sqlalchemy import func
        result = await self.session.execute(select(func.count(Meeting.id)))
        return result.scalar_one()

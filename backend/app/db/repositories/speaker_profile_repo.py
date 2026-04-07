from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.speaker_profile import SpeakerProfile
from app.db.repositories.base import BaseRepository


class SpeakerProfileRepository(BaseRepository[SpeakerProfile]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SpeakerProfile, session)

    async def list_all(self) -> list[SpeakerProfile]:
        result = await self.session.execute(
            select(SpeakerProfile).order_by(SpeakerProfile.name)
        )
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> SpeakerProfile | None:
        result = await self.session.execute(
            select(SpeakerProfile).where(SpeakerProfile.name == name)
        )
        return result.scalar_one_or_none()

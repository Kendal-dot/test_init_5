from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SpeakerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    audio_duration: float | None
    created_at: datetime


class SpeakerProfileListResponse(BaseModel):
    items: list[SpeakerProfileResponse]
    total: int

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.segment import SegmentResponse


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: str
    created_at: datetime
    updated_at: datetime
    segments: list[SegmentResponse] = []


class TranscriptExport(BaseModel):
    """JSON-exportformat för ett transkript."""
    meeting_id: str
    filename: str
    language: str
    duration: float | None
    source_type: str
    created_at: datetime
    model: str | None
    pipeline: str | None
    segments: list[dict]

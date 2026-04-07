from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transcript_id: int
    start_time: float
    end_time: float
    speaker_label: str | None
    text: str
    original_text: str
    is_edited: bool
    created_at: datetime
    updated_at: datetime


class SegmentUpdate(BaseModel):
    text: str


class SegmentSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transcript_id: int
    meeting_id: str
    start_time: float
    end_time: float
    speaker_label: str | None
    text: str

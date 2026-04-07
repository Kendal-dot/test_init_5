from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MeetingBase(BaseModel):
    original_filename: str
    language: str = "sv"
    source_type: Literal["upload", "live"] = "upload"


class MeetingCreate(MeetingBase):
    stored_filename: str
    file_path: str
    file_size_bytes: int | None = None


class MeetingResponse(MeetingBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    stored_filename: str
    file_size_bytes: int | None
    status: str
    duration: float | None
    model_used: str | None
    pipeline_used: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class MeetingListResponse(BaseModel):
    items: list[MeetingResponse]
    total: int
    limit: int
    offset: int

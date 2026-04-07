import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.transcript import Transcript


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    original_filename: Mapped[str] = mapped_column(String(512))
    stored_filename: Mapped[str] = mapped_column(String(512))
    file_path: Mapped[str] = mapped_column(String(1024))
    file_size_bytes: Mapped[int | None] = mapped_column(default=None)

    status: Mapped[str] = mapped_column(
        Enum("queued", "processing", "completed", "failed", name="job_status"),
        default="queued",
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        Enum("upload", "live", name="source_type"),
        default="upload",
    )

    language: Mapped[str] = mapped_column(String(10), default="sv")
    duration: Mapped[float | None] = mapped_column(default=None)
    model_used: Mapped[str | None] = mapped_column(String(256), default=None)
    pipeline_used: Mapped[str | None] = mapped_column(String(256), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    transcript: Mapped["Transcript | None"] = relationship(
        "Transcript", back_populates="meeting", uselist=False, cascade="all, delete-orphan"
    )

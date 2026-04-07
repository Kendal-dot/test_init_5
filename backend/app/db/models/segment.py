from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.transcript import Transcript


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transcript_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("transcripts.id", ondelete="CASCADE"), index=True
    )

    # Tidsmarkeringar i sekunder
    start_time: Mapped[float] = mapped_column(Float, index=True)
    end_time: Mapped[float] = mapped_column(Float)

    # Talare – generiska etiketter: "Talare 1", "Talare 2", etc.
    speaker_label: Mapped[str | None] = mapped_column(Text, default=None)

    # Text
    text: Mapped[str] = mapped_column(Text)
    original_text: Mapped[str] = mapped_column(Text)  # Sparas separat för att kunna återställa

    # Redigeringsstatus
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    transcript: Mapped["Transcript"] = relationship("Transcript", back_populates="segments")

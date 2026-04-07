"""
Transkriptservice – sparar pipeline-resultat och hanterar redigering/export.
"""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.segment import Segment
from app.db.models.transcript import Transcript
from app.db.repositories import MeetingRepository, SegmentRepository, TranscriptRepository
from app.pipeline.interface import TranscriptionResult
from app.schemas.transcript import TranscriptExport

logger = get_logger(__name__)
settings = get_settings()


def _format_timestamp(seconds: float) -> str:
    """Formatera sekunder som HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def generate_txt_export(
    filename: str,
    meeting_id: str,
    duration: float | None,
    source_type: str,
    created_at: datetime,
    model_used: str | None,
    segments: list[dict],
) -> str:
    """
    Generera ren TXT för vektordatabas-indexering.

    Format:
    ---
    Möte: <filnamn>
    Datum: 2026-04-07 14:30
    Längd: 45:12
    Källa: upload
    Modell: KBLab/kb-whisper-small
    Segment: 127
    ---

    [00:00 - 00:15] Kendal:
    Vi behöver diskutera budgeten för nästa kvartal.

    [00:15 - 00:28] Anna:
    Ja, jag tycker vi borde öka marknadsföringen.
    """
    lines = []

    lines.append("---")
    lines.append(f"Möte: {filename}")
    lines.append(f"ID: {meeting_id}")
    if created_at:
        lines.append(f"Datum: {created_at.strftime('%Y-%m-%d %H:%M')}")
    if duration:
        lines.append(f"Längd: {_format_timestamp(duration)}")
    lines.append(f"Källa: {source_type}")
    if model_used:
        lines.append(f"Modell: {model_used}")
    lines.append(f"Segment: {len(segments)}")
    lines.append("---")
    lines.append("")

    for seg in segments:
        start = _format_timestamp(seg["start"])
        end = _format_timestamp(seg["end"])
        speaker = seg.get("speaker") or "Okänd"
        text = seg.get("text", "").strip()

        lines.append(f"[{start} - {end}] {speaker}:")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def generate_json_export(
    filename: str,
    meeting_id: str,
    duration: float | None,
    source_type: str,
    created_at: datetime,
    model_used: str | None,
    segments: list[dict],
) -> dict:
    """
    Generera strukturerad JSON för vektordatabas-indexering.

    Varje segment är ett eget objekt med all metadata – redo att
    chunkas och embedda direkt utan extra parsing.
    """
    return {
        "meeting_id": meeting_id,
        "title": filename,
        "date": created_at.strftime("%Y-%m-%d %H:%M") if created_at else None,
        "duration_seconds": duration,
        "source_type": source_type,
        "model": model_used,
        "total_segments": len(segments),
        "segments": [
            {
                "index": i,
                "start": seg["start"],
                "end": seg["end"],
                "start_formatted": _format_timestamp(seg["start"]),
                "end_formatted": _format_timestamp(seg["end"]),
                "speaker": seg.get("speaker") or "Okänd",
                "text": seg.get("text", "").strip(),
            }
            for i, seg in enumerate(segments)
        ],
    }


def save_export_files(
    meeting_id: str,
    filename: str,
    duration: float | None,
    source_type: str,
    created_at: datetime,
    model_used: str | None,
    segments: list[dict],
) -> None:
    """Spara både TXT och JSON till exports-katalogen."""
    import json as json_lib

    exports_dir = Path(settings.resolved_exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    args = dict(
        filename=filename,
        meeting_id=meeting_id,
        duration=duration,
        source_type=source_type,
        created_at=created_at,
        model_used=model_used,
        segments=segments,
    )

    # TXT
    txt_path = exports_dir / f"transcript_{meeting_id}.txt"
    txt_path.write_text(generate_txt_export(**args), encoding="utf-8")
    logger.info(f"TXT-export sparad: {txt_path}")

    # JSON
    json_path = exports_dir / f"transcript_{meeting_id}.json"
    json_data = generate_json_export(**args)
    json_path.write_text(
        json_lib.dumps(json_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"JSON-export sparad: {json_path}")


async def save_transcription_result(
    session: AsyncSession,
    meeting_id: str,
    result: TranscriptionResult,
) -> Transcript:
    """Spara ett TranscriptionResult till databasen."""
    meeting_repo = MeetingRepository(session)
    transcript_repo = TranscriptRepository(session)
    segment_repo = SegmentRepository(session)

    # Uppdatera mötesstatus och metadata
    meeting = await meeting_repo.update_after_transcription(
        meeting_id,
        duration=result.duration,
        model_used=result.model_used,
        pipeline_used=result.pipeline_used,
    )

    # Skapa eller uppdatera transkriptobjektet
    existing = await transcript_repo.get_by_meeting_id(meeting_id)
    if existing:
        transcript = existing
    else:
        transcript = Transcript(meeting_id=meeting_id)
        transcript = await transcript_repo.create(transcript)

    # Spara segment
    segments = [
        Segment(
            transcript_id=transcript.id,
            start_time=seg.start,
            end_time=seg.end,
            speaker_label=seg.speaker,
            text=seg.text,
            original_text=seg.text,
            is_edited=False,
        )
        for seg in result.segments
    ]
    await segment_repo.bulk_create(segments)
    logger.info(
        f"Sparade {len(segments)} segment för meeting_id={meeting_id}"
    )

    # Generera TXT + JSON-export automatiskt
    try:
        save_export_files(
            meeting_id=meeting_id,
            filename=meeting.original_filename if meeting else meeting_id,
            duration=result.duration,
            source_type=meeting.source_type if meeting else "upload",
            created_at=meeting.created_at if meeting else datetime.now(timezone.utc),
            model_used=result.model_used,
            segments=[
                {"start": seg.start, "end": seg.end, "speaker": seg.speaker, "text": seg.text}
                for seg in result.segments
            ],
        )
    except Exception as exc:
        logger.warning(f"Kunde inte skapa exportfiler: {exc}")

    return transcript


async def update_segment_text(
    session: AsyncSession, segment_id: int, new_text: str
) -> Segment | None:
    repo = SegmentRepository(session)
    return await repo.update_text(segment_id, new_text)


async def get_transcript_export(
    session: AsyncSession, meeting_id: str
) -> TranscriptExport | None:
    meeting_repo = MeetingRepository(session)
    transcript_repo = TranscriptRepository(session)

    meeting = await meeting_repo.get(meeting_id)
    if not meeting:
        return None

    transcript = await transcript_repo.get_by_meeting_id(meeting_id)
    if not transcript:
        return None

    transcript_with_segs = await transcript_repo.get_with_segments(transcript.id)

    return TranscriptExport(
        meeting_id=meeting_id,
        filename=meeting.original_filename,
        language=meeting.language,
        duration=meeting.duration,
        source_type=meeting.source_type,
        created_at=meeting.created_at,
        model=meeting.model_used,
        pipeline=meeting.pipeline_used,
        segments=[
            {
                "id": seg.id,
                "start": seg.start_time,
                "end": seg.end_time,
                "speaker": seg.speaker_label,
                "text": seg.text,
                "is_edited": seg.is_edited,
            }
            for seg in transcript_with_segs.segments
        ],
    )

"""
Talaridentifiering med pyannote.audio.

Kräver:
- HF_TOKEN i .env med åtkomst till pyannote/speaker-diarization-3.1
- Accepterade villkor på: https://huggingface.co/pyannote/speaker-diarization-3.1

Om DIARIZATION_ENABLED=false returneras tomma talarsegment och
alla segment märks utan talare (frontend visar "Okänd talare").
"""

from dataclasses import dataclass

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class DiarizationSegment:
    start: float
    end: float
    speaker_id: str  # ex. "SPEAKER_00", "SPEAKER_01"


def assign_speaker_labels(
    diarization_segments: list[DiarizationSegment],
) -> dict[str, str]:
    """
    Mappar pyannote speaker-id → "Talare 1", "Talare 2", etc.
    Ordning baseras på första förekomst i tid.
    """
    mapping: dict[str, str] = {}
    counter = 1
    for seg in sorted(diarization_segments, key=lambda s: s.start):
        if seg.speaker_id not in mapping:
            mapping[seg.speaker_id] = f"Talare {counter}"
            counter += 1
    return mapping


def find_speaker_for_segment(
    seg_start: float,
    seg_end: float,
    diarization: list[DiarizationSegment],
    label_map: dict[str, str],
) -> str | None:
    """
    Hittar vilken talare som dominerar ett transkriptsegment.
    Väljer det diarization-segment med störst överlapp.
    """
    if not diarization:
        return None

    best_speaker = None
    best_overlap = 0.0

    for d in diarization:
        overlap_start = max(seg_start, d.start)
        overlap_end = min(seg_end, d.end)
        overlap = max(0.0, overlap_end - overlap_start)
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = label_map.get(d.speaker_id)

    return best_speaker


class DiarizationService:
    """Wrapper runt pyannote.audio speaker diarization."""

    def __init__(self) -> None:
        self._pipeline = None

    def _load_pipeline(self):
        if self._pipeline is not None:
            return

        if not settings.hf_token:
            raise RuntimeError(
                "HF_TOKEN saknas. Sätt HF_TOKEN i .env för att använda diarization. "
                "Acceptera även villkoren för pyannote/speaker-diarization-3.1 på HuggingFace."
            )

        from pyannote.audio import Pipeline
        import torch

        logger.info("Laddar pyannote speaker-diarization pipeline...")
        self._pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=settings.hf_token,
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._pipeline = self._pipeline.to(torch.device(device))
        logger.info(f"pyannote pipeline laddad på {device}")

    def diarize(
        self, wav_path: str
    ) -> list[DiarizationSegment]:
        """
        Kör diarization på en WAV-fil.
        Returnerar lista med DiarizationSegment.
        """
        self._load_pipeline()

        kwargs = {}
        if settings.min_speakers > 0:
            kwargs["min_speakers"] = settings.min_speakers
        if settings.max_speakers > 0:
            kwargs["max_speakers"] = settings.max_speakers

        diarization = self._pipeline(wav_path, **kwargs)

        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(
                DiarizationSegment(
                    start=turn.start,
                    end=turn.end,
                    speaker_id=speaker,
                )
            )

        logger.info(
            f"Diarization klar: {len(segments)} segment, "
            f"{len({s.speaker_id for s in segments})} talare"
        )
        return segments


def identify_speakers_by_profile(
    wav_path: str,
    diarization_segments: list[DiarizationSegment],
    label_map: dict[str, str],
    profiles: list[dict],
) -> dict[str, str]:
    """
    Matcha diarization-kluster mot sparade röstprofiler.

    Extraherar en embedding per unik talare (SPEAKER_XX) och jämför
    mot alla profiler. Om en match hittas ersätts "Talare N" med
    det registrerade namnet.

    Returnerar en uppdaterad label_map: {"SPEAKER_00": "Kendal", "SPEAKER_01": "Talare 2"}.
    """
    if not profiles or not diarization_segments:
        return label_map

    from app.pipeline.speaker_embedding import (
        extract_cluster_embedding,
        match_embedding_to_profiles,
    )

    unique_speakers = set(s.speaker_id for s in diarization_segments)
    updated_map = dict(label_map)
    used_profile_names: set[str] = set()

    for spk_id in unique_speakers:
        cluster_segs = [
            {"start": s.start, "end": s.end}
            for s in diarization_segments
            if s.speaker_id == spk_id
        ]
        try:
            embedding = extract_cluster_embedding(wav_path, cluster_segs)
            available_profiles = [
                p for p in profiles if p["name"] not in used_profile_names
            ]
            name, score = match_embedding_to_profiles(embedding, available_profiles)
            if name:
                updated_map[spk_id] = name
                used_profile_names.add(name)
                logger.info(
                    f"Identifierad: {spk_id} → '{name}' (score={score:.3f})"
                )
        except Exception as exc:
            logger.warning(f"Kunde inte extrahera embedding för {spk_id}: {exc}")

    return updated_map


# Singleton för att undvika att ladda om modellen
_diarization_service: DiarizationService | None = None


def get_diarization_service() -> DiarizationService:
    global _diarization_service
    if _diarization_service is None:
        _diarization_service = DiarizationService()
    return _diarization_service

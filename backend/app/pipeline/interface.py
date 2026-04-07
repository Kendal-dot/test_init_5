"""
Abstrakt pipeline-interface.

Alla pipeline-implementationer (easytranscriber, mock, framtida alternativ)
ska implementera TranscriptionPipeline och returnera TranscriptionResult.
Detta isolerar resten av systemet från pipeline-specifik kod.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SegmentResult:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass
class TranscriptionResult:
    segments: list[SegmentResult] = field(default_factory=list)
    duration: float | None = None
    language: str = "sv"
    model_used: str = ""
    pipeline_used: str = ""


class TranscriptionPipeline(ABC):
    """Abstrakt bas för transkriberingspipelines."""

    @abstractmethod
    async def transcribe(
        self,
        file_path: str,
        speaker_profiles: list[dict] | None = None,
    ) -> TranscriptionResult:
        """
        Transkribera en ljudfil. Returnerar strukturerat resultat.
        speaker_profiles: lista av {"name": str, "embedding": list[float]}
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Returnerar True om pipelinen kan initieras (modeller tillgängliga, etc.)."""
        ...

"""
Pipeline-adapter för KB-Whisper via easytranscriber.

Flöde:
1. Konvertera input → WAV 16kHz mono (ffmpeg)
2. Kör easytranscriber pipeline (VAD + KB-Whisper + forced alignment)
3. Om diarization är aktiverat: kör pyannote och matcha talare mot segment
4. Returnera TranscriptionResult

Varför easytranscriber + KB-Whisper?
- KB-Whisper är specifikt fintränad på >50.000h svensk tal
- Minskar WER med 47% jämfört med OpenAI whisper-large-v3
- easytranscriber ger GPU-accelererade word-level timestamps
- Silero VAD kräver ingen HuggingFace-autentisering (bättre för lokal MVP)
"""

import asyncio
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.pipeline.audio_utils import convert_to_wav
from app.pipeline.interface import SegmentResult, TranscriptionPipeline, TranscriptionResult

logger = get_logger(__name__)
settings = get_settings()

PIPELINE_NAME = "easytranscriber-v1"


class EasytranscriberAdapter(TranscriptionPipeline):
    """
    Adapter för easytranscriber med KB-Whisper.
    Modellen laddas lazy vid första anropet och cachas i process.
    """

    def __init__(self) -> None:
        self._pipeline_loaded = False

    def is_available(self) -> bool:
        try:
            import easytranscriber  # noqa: F401
            return True
        except ImportError:
            return False

    async def transcribe(
        self,
        file_path: str,
        speaker_profiles: list[dict] | None = None,
    ) -> TranscriptionResult:
        """Kör fullständig transkriberingspipeline för en fil."""
        logger.info(f"Startar transkribering: {file_path}")

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = str(Path(tmpdir) / "audio.wav")

            # Steg 1: Konvertera till WAV
            duration = await convert_to_wav(file_path, wav_path)
            logger.info(f"Audio konverterad: {duration:.1f}s")

            # Steg 2: Kör easytranscriber
            loop = asyncio.get_event_loop()
            raw_segments = await loop.run_in_executor(
                None, self._run_pipeline, wav_path, tmpdir
            )

            # Steg 3: Talaridentifiering via diarization
            speaker_map = {}
            diarization_segments = []
            if settings.diarization_enabled:
                try:
                    diarization_segments, speaker_map = await loop.run_in_executor(
                        None, self._run_diarization, wav_path
                    )
                except Exception as exc:
                    logger.warning(f"Diarization misslyckades, fortsätter utan: {exc}")

            # Steg 3b: Matcha kluster mot sparade röstprofiler
            if diarization_segments and speaker_profiles:
                try:
                    from app.pipeline.diarization import identify_speakers_by_profile
                    speaker_map = await loop.run_in_executor(
                        None,
                        identify_speakers_by_profile,
                        wav_path, diarization_segments, speaker_map, speaker_profiles,
                    )
                    logger.info("Röstprofiler matchade mot diarization-kluster")
                except Exception as exc:
                    logger.warning(f"Röstprofilmatchning misslyckades: {exc}")

        # Steg 4: Bygg resultat
        from app.pipeline.diarization import find_speaker_for_segment
        segments = []
        for seg in raw_segments:
            speaker = find_speaker_for_segment(
                seg["start"], seg["end"], diarization_segments, speaker_map
            ) if diarization_segments else None

            segments.append(SegmentResult(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"].strip(),
                speaker=speaker,
            ))

        logger.info(f"Transkribering klar: {len(segments)} segment")
        return TranscriptionResult(
            segments=segments,
            duration=duration,
            language="sv",
            model_used=settings.transcription_model,
            pipeline_used=PIPELINE_NAME,
        )

    def _run_pipeline(self, wav_path: str, output_dir: str) -> list[dict]:
        """
        Kör easytranscriber pipeline synkront (körs i executor-tråd).
        Returnerar lista av {start, end, text}.
        """
        import json
        from pathlib import Path

        from easytranscriber.pipelines import pipeline
        from easyaligner.text import load_tokenizer

        audio_filename = Path(wav_path).name
        audio_dir = str(Path(wav_path).parent)

        tokenizer = load_tokenizer("swedish")

        pipeline(
            vad_model=settings.vad_backend,      # "silero" kräver ingen autentisering
            emissions_model="KBLab/wav2vec2-large-voxrex-swedish",  # Swedish wav2vec2
            transcription_model=settings.transcription_model,
            audio_paths=[audio_filename],
            audio_dir=audio_dir,
            language="sv",
            tokenizer=tokenizer,
            cache_dir=str(settings.models_cache_dir),
            output_dir=output_dir,
        )

        # Läs utdata från alignments-katalog
        alignment_file = Path(output_dir) / "alignments" / Path(audio_filename).with_suffix(".json").name
        if not alignment_file.exists():
            logger.warning(f"Alignment-fil saknas: {alignment_file}")
            return []

        with open(alignment_file, encoding="utf-8") as f:
            data = json.load(f)

        return self._parse_alignment_output(data)

    def _parse_alignment_output(self, data: dict) -> list[dict]:
        """
        Parsar easytranscribers JSON-utdata till lista av segment.
        Strukturen: data["speech_segments"][i]["alignment_segments"][j]
        """
        segments = []
        for speech_seg in data.get("speech_segments", []):
            for align_seg in speech_seg.get("alignment_segments", []):
                text = align_seg.get("text", "").strip()
                if not text:
                    continue
                segments.append({
                    "start": align_seg.get("start", 0.0),
                    "end": align_seg.get("end", 0.0),
                    "text": text,
                })
        return segments

    def _run_diarization(self, wav_path: str) -> tuple[list, dict]:
        """Kör pyannote diarization synkront (körs i executor-tråd)."""
        from app.pipeline.diarization import (
            assign_speaker_labels,
            get_diarization_service,
        )
        service = get_diarization_service()
        diar_segments = service.diarize(wav_path)
        label_map = assign_speaker_labels(diar_segments)
        return diar_segments, label_map

"""
Röstprofilering med speechbrain ECAPA-TDNN.

Extraherar speaker embeddings (röstfingeravtryck) som kan lagras och
jämföras för att identifiera talare vid framtida transkribering.

ECAPA-TDNN ger en 192-dimensionell vektor per talsegment.
Cosine similarity > 0.25 innebär i regel samma talare.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import torch

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_classifier = None


def _get_classifier():
    """Ladda ECAPA-TDNN en gång och cacha."""
    global _classifier
    if _classifier is not None:
        return _classifier

    from speechbrain.inference.speaker import EncoderClassifier

    # Använd standard HuggingFace-cache (~/.cache/huggingface/) istället för
    # anpassad savedir – Windows kräver admin-privilegier för symlinks
    # som speechbrain skapar vid custom savedir.
    logger.info("Laddar speaker embedding-modell (ECAPA-TDNN)...")
    _classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
    )
    logger.info("Speaker embedding-modell redo")
    return _classifier


def _get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def _convert_to_wav_16k(input_bytes: bytes) -> np.ndarray:
    """Konverterar godtycklig audio till 16kHz mono float32 via ffmpeg."""
    ffmpeg = _get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-i", "pipe:0",
        "-ar", "16000",
        "-ac", "1",
        "-f", "f32le",
        "pipe:1",
    ]
    result = subprocess.run(cmd, input=input_bytes, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg misslyckades: {result.stderr.decode(errors='replace')}")
    audio = np.frombuffer(result.stdout, dtype=np.float32).copy()
    if audio.size == 0:
        raise RuntimeError("Tomt ljud – inspelningen innehåller inget tal")
    return audio


def _convert_wav_file_to_array(wav_path: str) -> np.ndarray:
    """Läser en WAV-fil till 16kHz mono float32."""
    ffmpeg = _get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-i", wav_path,
        "-ar", "16000",
        "-ac", "1",
        "-f", "f32le",
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg misslyckades: {result.stderr.decode(errors='replace')}")
    return np.frombuffer(result.stdout, dtype=np.float32).copy()


def extract_embedding_from_bytes(audio_bytes: bytes) -> list[float]:
    """
    Extraherar en speaker embedding från rå audio-bytes.
    Returnerar en lista med 192 floats.
    """
    audio = _convert_to_wav_16k(audio_bytes)
    return _extract_embedding_from_array(audio)


def extract_embedding_from_wav(wav_path: str) -> list[float]:
    """Extraherar en speaker embedding från en WAV-fil."""
    audio = _convert_wav_file_to_array(wav_path)
    return _extract_embedding_from_array(audio)


def _extract_embedding_from_array(audio: np.ndarray) -> list[float]:
    """Kärnan: kör ECAPA-TDNN på en float32-array."""
    classifier = _get_classifier()
    waveform = torch.tensor(audio).unsqueeze(0)  # (1, samples)
    with torch.no_grad():
        embedding = classifier.encode_batch(waveform)
    return embedding.squeeze().cpu().tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Beräkna cosine similarity mellan två embeddings."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm == 0:
        return 0.0
    return float(dot / norm)


# Tröskel för "samma talare". ECAPA-TDNN med cosine similarity:
# > 0.25 → sannolikt samma person
# > 0.40 → hög säkerhet
MATCH_THRESHOLD = 0.25
HIGH_CONFIDENCE_THRESHOLD = 0.40


def match_embedding_to_profiles(
    embedding: list[float],
    profiles: list[dict],
) -> tuple[str | None, float]:
    """
    Matcha en embedding mot sparade profiler.

    profiles: lista av {"name": str, "embedding": list[float]}
    Returnerar (namn, score) eller (None, 0.0) om ingen match.
    """
    if not profiles:
        return None, 0.0

    best_name = None
    best_score = 0.0

    for profile in profiles:
        score = cosine_similarity(embedding, profile["embedding"])
        if score > best_score:
            best_score = score
            best_name = profile["name"]

    if best_score >= MATCH_THRESHOLD:
        confidence = "hög" if best_score >= HIGH_CONFIDENCE_THRESHOLD else "medel"
        logger.info(f"Talaridentifiering: '{best_name}' (score={best_score:.3f}, {confidence})")
        return best_name, best_score

    logger.debug(f"Ingen match hittad (bästa score={best_score:.3f} < {MATCH_THRESHOLD})")
    return None, best_score


def extract_cluster_embedding(
    wav_path: str,
    segments: list[dict],
) -> list[float]:
    """
    Extraherar en embedding för ett kluster av segment ur en WAV-fil.
    Väljer det längsta segmentet (mest representativt).

    segments: lista av {"start": float, "end": float}
    """
    if not segments:
        raise ValueError("Inga segment att extrahera embedding från")

    longest = max(segments, key=lambda s: s["end"] - s["start"])

    ffmpeg = _get_ffmpeg_exe()
    start = longest["start"]
    duration = longest["end"] - longest["start"]
    duration = min(duration, 30.0)

    cmd = [
        ffmpeg, "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", wav_path,
        "-ar", "16000",
        "-ac", "1",
        "-f", "f32le",
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg misslyckades: {result.stderr.decode(errors='replace')}")

    audio = np.frombuffer(result.stdout, dtype=np.float32).copy()
    if audio.size == 0:
        raise RuntimeError("Tomt kluster-segment")

    return _extract_embedding_from_array(audio)

"""
Hjälpfunktioner för ljudbearbetning.
Konverterar video/audio till WAV 16kHz mono via ffmpeg.
"""

import asyncio
import subprocess
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


async def convert_to_wav(input_path: str, output_path: str) -> float:
    """
    Konverterar en ljud- eller videofil till WAV 16kHz mono med ffmpeg.
    Returnerar filens längd i sekunder.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-f", "wav",
        output_path,
    ]

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(cmd, capture_output=True, text=True),
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg misslyckades: {result.stderr}")

    duration = await get_audio_duration(output_path)
    logger.debug(f"Konverterade {input_path} → {output_path} ({duration:.1f}s)")
    return duration


async def get_audio_duration(wav_path: str) -> float:
    """Hämtar längd i sekunder med ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        wav_path,
    ]
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(cmd, capture_output=True, text=True),
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0

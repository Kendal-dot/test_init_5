"""
Röstprofilservice – hanterar enrollment och matchning av talare.
"""

import asyncio
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.speaker_profile import SpeakerProfile
from app.db.repositories import SpeakerProfileRepository

logger = get_logger(__name__)


async def enroll_speaker(
    session: AsyncSession,
    name: str,
    audio_bytes: bytes,
) -> SpeakerProfile:
    """
    Registrera en talares röstprofil.
    Extraherar embedding från inspelat ljud och sparar i databasen.
    """
    from app.pipeline.speaker_embedding import (
        extract_embedding_from_bytes,
        _convert_to_wav_16k,
    )

    loop = asyncio.get_event_loop()

    # Extrahera embedding i executor (CPU-intensivt)
    embedding = await loop.run_in_executor(
        None, extract_embedding_from_bytes, audio_bytes
    )

    # Beräkna duration
    audio_array = await loop.run_in_executor(
        None, _convert_to_wav_16k, audio_bytes
    )
    duration = len(audio_array) / 16000.0

    repo = SpeakerProfileRepository(session)

    # Ta bort befintlig profil med samma namn (uppdatera)
    existing = await repo.get_by_name(name)
    if existing:
        await repo.delete(existing)
        logger.info(f"Ersätter befintlig röstprofil för '{name}'")

    profile = SpeakerProfile(
        name=name,
        embedding_json=json.dumps(embedding),
        audio_duration=duration,
    )
    profile = await repo.create(profile)
    logger.info(f"Röstprofil sparad: '{name}' ({duration:.1f}s, {len(embedding)} dim)")
    return profile


async def get_all_profiles_with_embeddings(
    session: AsyncSession,
) -> list[dict]:
    """
    Hämta alla profiler med deras embeddings.
    Returnerar lista av {"name": str, "embedding": list[float]}.
    """
    repo = SpeakerProfileRepository(session)
    profiles = await repo.list_all()
    return [
        {"name": p.name, "embedding": json.loads(p.embedding_json)}
        for p in profiles
    ]

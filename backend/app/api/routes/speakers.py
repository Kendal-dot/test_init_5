from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.repositories import SpeakerProfileRepository
from app.schemas.speaker_profile import SpeakerProfileListResponse, SpeakerProfileResponse
from app.services.speaker_service import enroll_speaker

router = APIRouter(prefix="/speakers", tags=["speakers"])


@router.post("/enroll", response_model=SpeakerProfileResponse, status_code=201)
async def enroll(
    name: str = Form(..., min_length=1, max_length=256),
    audio: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
):
    """
    Registrera en röstprofil.
    Skicka namn + en ljudinspelning (minst 10 sekunder).
    """
    audio_bytes = await audio.read()
    if len(audio_bytes) < 1000:
        raise HTTPException(status_code=400, detail="Inspelningen är för kort")

    try:
        profile = await enroll_speaker(session, name.strip(), audio_bytes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Kunde inte bearbeta ljudet: {exc}")

    return profile


@router.get("", response_model=SpeakerProfileListResponse)
async def list_profiles(session: AsyncSession = Depends(get_db)):
    """Lista alla registrerade röstprofiler."""
    repo = SpeakerProfileRepository(session)
    profiles = await repo.list_all()
    return SpeakerProfileListResponse(items=profiles, total=len(profiles))


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: str, session: AsyncSession = Depends(get_db)):
    """Ta bort en röstprofil."""
    repo = SpeakerProfileRepository(session)
    profile = await repo.get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil hittades inte")
    await repo.delete(profile)

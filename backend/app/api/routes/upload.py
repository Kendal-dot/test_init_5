from fastapi import APIRouter, UploadFile, File, HTTPException

from app.schemas.meeting import MeetingResponse
from app.services.job_service import create_upload_job

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=MeetingResponse, status_code=201)
async def upload_file(file: UploadFile = File(...)):
    """
    Ladda upp en ljud- eller videofil för transkribering.
    Filen sparas lokalt och ett transkriberingsjobb skapas i kön.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filnamn saknas")
    return await create_upload_job(file)

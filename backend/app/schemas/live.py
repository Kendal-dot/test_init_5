from pydantic import BaseModel


class LiveSegmentInput(BaseModel):
    speaker: str
    start: float
    end: float
    text: str


class SaveLiveSessionRequest(BaseModel):
    title: str | None = None          # Valfritt mötesnamn, ex. "Teammöte 2026-04-07"
    participants: list[str] = []       # Registrerade deltagare (metadata)
    segments: list[LiveSegmentInput]

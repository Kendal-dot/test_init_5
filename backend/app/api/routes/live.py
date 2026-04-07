"""
Live-transkribering via WebSocket.

Protokoll:
1. Klient skickar (valfritt) JSON-init med deltagarnamn:
   {"type": "init", "participants": ["Kendal", "Marcus", "Anna"]}
2. Klient skickar binärdata: valfritt audioformat (WebM/Opus etc.)
3. Server svarar med JSON: {"text": "...", "speaker": "Kendal", "start": 0.0, "end": 3.0}
4. Klient skickar textsträngen "STOP" för att avsluta sessionen rent

Med förregistrerade deltagare räcker kortare fraser för identifiering:
  "Kendal här", "det är Marcus", "Anna talar" etc.
"""

import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.core.logging import get_logger
from app.db.base import get_db
from app.schemas.live import SaveLiveSessionRequest
from app.schemas.meeting import MeetingResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/live", tags=["live"])


@router.post("/save", response_model=MeetingResponse, status_code=201)
async def save_live_session(
    body: SaveLiveSessionRequest,
    session: AsyncSession = Depends(get_db),
):
    """Spara en live-transkriberingssession till databasen."""
    from app.services.live_service import save_live_session as _save
    meeting = await _save(session, body)
    return meeting


async def _safe_send_json(websocket: WebSocket, data: dict) -> bool:
    """Skicka JSON om anslutningen fortfarande är öppen. Returnerar False vid disconnect."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json(data)
            return True
    except (WebSocketDisconnect, RuntimeError):
        pass
    return False


@router.websocket("/transcribe")
async def live_transcribe(websocket: WebSocket):
    await websocket.accept()
    logger.info("Live WebSocket-anslutning öppnad")

    from app.pipeline.live_adapter import LiveTranscriptionAdapter
    adapter = LiveTranscriptionAdapter()
    chunk_index = 0

    # Ladda sparade röstprofiler vid anslutning
    try:
        from app.db.base import AsyncSessionLocal
        from app.services.speaker_service import get_all_profiles_with_embeddings
        async with AsyncSessionLocal() as session:
            profiles = await get_all_profiles_with_embeddings(session)
        adapter.set_voice_profiles(profiles)
    except Exception as exc:
        logger.warning(f"Kunde inte ladda röstprofiler för live-session: {exc}")

    try:
        while True:
            try:
                data = await websocket.receive()
            except WebSocketDisconnect:
                logger.info("Klient kopplade ner")
                break

            if data.get("type") == "websocket.disconnect":
                break

            # --- Text-meddelanden ---
            if "text" in data:
                text_msg = data["text"]

                if text_msg == "STOP":
                    logger.info("Live-session avslutad av klient (STOP)")
                    break

                # Init-meddelande med deltagarnamn
                try:
                    payload = json.loads(text_msg)
                    if payload.get("type") == "init":
                        participants = payload.get("participants", [])
                        adapter.set_participants(participants)
                        logger.info(f"Init mottaget – deltagare: {participants}")
                        await _safe_send_json(websocket, {
                            "type": "init_ack",
                            "participants": participants,
                        })
                    else:
                        logger.debug(f"Okänt text-meddelande: {text_msg[:80]}")
                except (json.JSONDecodeError, AttributeError):
                    logger.debug(f"Kunde inte parsa text-meddelande: {text_msg[:80]}")
                continue

            # --- Binär audio-data ---
            audio_bytes = data.get("bytes")
            if not audio_bytes:
                continue

            chunk_index += 1
            logger.debug(f"Mottog chunk #{chunk_index}: {len(audio_bytes)} bytes")

            result = await adapter.transcribe_chunk(audio_bytes, chunk_index)
            sent = await _safe_send_json(websocket, result)
            if not sent:
                logger.info("Klient ej nåbar, avslutar session")
                break

    except Exception as exc:
        logger.exception(f"Oväntat fel i live WebSocket: {exc}")
    finally:
        logger.info(f"Live-session avslutad efter {chunk_index} chunks")

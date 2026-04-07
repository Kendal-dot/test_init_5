"""
Live-transkribering adapter.

Pseudo-live: tar emot en audio-chunk i valfritt format (WebM/Opus från
MediaRecorder, WAV etc.), konverterar via ffmpeg till 16kHz mono PCM,
kör KB-Whisper inferens och returnerar text direkt.

Modellen cachas som singleton – laddas en gång per process, inte per anslutning.

Talaridentifiering via nyckelord (SpeakerTracker):
  Talare meddelar sig via röstkommandon som Whisper transkriberar:
  - "Nu talar Marcus"  → aktiv talare = "Marcus"
  - "Jag heter Anna"  → aktiv talare = "Anna"
  - "Klart slut"       → aktiv talare avslutar sin tur
  Nyckelorden tas bort från den visade texten.
"""

import asyncio
import re
import subprocess

import numpy as np
import torch

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Nyckelords-baserad talaridentifiering
# ---------------------------------------------------------------------------

# Mönster som identifierar en ny talare. Grupp 1 = talarens namn.
_START_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bnu talar\s+(\w+)\b", re.IGNORECASE),
    re.compile(r"\bjag heter\s+(\w+)\b", re.IGNORECASE),
    re.compile(r"\bhär är\s+(\w+)\b", re.IGNORECASE),
    re.compile(r"\bdet är\s+(\w+)\s+som talar\b", re.IGNORECASE),
    re.compile(r"\b(\w+)\s+talar\s+nu\b", re.IGNORECASE),
    re.compile(r"\bjag är\s+(\w+)\b", re.IGNORECASE),
]

# Mönster som extraherar ett potentiellt namn ur typiska talarfraser.
# Grupp 1 = det ord som sannolikt är ett namn.
_NAME_EXTRACTORS: list[re.Pattern] = [
    re.compile(r"\b(\w+)\s+här\b", re.IGNORECASE),           # "Kendal här"
    re.compile(r"\b(\w+)\s+talar\b", re.IGNORECASE),         # "Kendal talar"
    re.compile(r"\bnu\s+talar\s+(\w+)\b", re.IGNORECASE),    # "Nu talar Kendal"
    re.compile(r"\bhär\s+är\s+(\w+)\b", re.IGNORECASE),      # "Här är Kendal"
    re.compile(r"\bdet\s+är\s+(\w+)\b", re.IGNORECASE),      # "Det är Kendal"
    re.compile(r"\bjag\s+är\s+(\w+)\b", re.IGNORECASE),      # "Jag är Kendal"
    re.compile(r"^\s*(\w+)[.,!?]?\s*$", re.IGNORECASE),      # Bara ett ord ensamt
]

# Mönster som signalerar att aktiv talare avslutar sin tur
_END_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bklart[\s,.]*(slut|över)\b", re.IGNORECASE),
    re.compile(r"\bslut[\s,.]*klart\b", re.IGNORECASE),
    re.compile(r"\böver[\s,.]*och[\s,.]*slut\b", re.IGNORECASE),
    re.compile(r"\bjag[\s,.]*är[\s,.]*klar\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Fonetisk namnormalisering
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """
    Normaliserar ett namn till en fonetisk basform för matchning.
    Hanterar vanliga svenska stavningsvarianter:
      Kendall/Kendal → kendal
      Philip/Phillip/Filip → filip
      Christoffer/Kristoffer → kristofer
      Sara/Sarah → sara
      Mikael/Michael → mikael
      Wilhelm/Vilhelm → vilhelm
    """
    n = name.lower().strip()
    # Behåll bara bokstäver (tar bort bindestreck, apostrof etc.)
    n = re.sub(r"[^a-zåäöéàü]", "", n)
    # Sammansatta substitutioner – ordning spelar roll
    n = n.replace("sch", "sk")      # Schiller → skiler
    n = n.replace("ch", "k")        # Christoffer → kristoffer
    n = n.replace("ph", "f")        # Philip → filip
    n = n.replace("ck", "k")        # Erick → erik
    n = n.replace("qv", "kv")       # Qvist → kvist
    n = n.replace("qu", "kv")
    n = n.replace("x", "ks")        # Alex → aleks
    n = n.replace("z", "s")         # Zara → sara
    # Enstaka bokstavsbyten
    n = n.replace("w", "v")         # Wilhelm → vilhelm
    # Stumma bokstäver i slutposition: h, e
    if n.endswith("h"):
        n = n[:-1]                  # Sarah → sara, Leah → lea
    if n.endswith("e") and len(n) > 3:
        n = n[:-1]                  # Abbie → abi (behandlas av collapse nedan)
    # Kollaps av dubbelkonsonanter/vokaler: ll→l, ss→s, aa→a, etc.
    n = re.sub(r"(.)\1+", r"\1", n)
    return n


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein-avstånd – antal insättningar/borttagningar/byten."""
    if len(a) < len(b):
        return _edit_distance(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for ca in a:
        curr = [prev[0] + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


def _name_matches(transcribed: str, canonical: str, normalized_canonical: str) -> bool:
    """
    Returnerar True om det transkriberade ordet sannolikt är samma namn
    som det registrerade canoniska namnet.
    Strategi:
      1. Normalisera det transkriberade ordet och jämför direkt
      2. Om inte exakt match – tillåt edit-avstånd 1 för namn > 4 tecken
    """
    norm_t = _normalize_name(transcribed)
    if norm_t == normalized_canonical:
        return True
    # Tillåt ett enskilt fel (extra bokstav, fel vokal etc.) i längre namn
    if len(normalized_canonical) >= 4 and _edit_distance(norm_t, normalized_canonical) <= 1:
        return True
    return False


class SpeakerTracker:
    """
    Håller talarstate per WebSocket-session.
    Parsar nyckelord ur transkriberad text och returnerar rengjord text + talarnamn.

    Talaridentifiering sker i två lager:
    1. Extrahera potentiellt namn ur typiska fraser ("Kendal här", "Nu talar Anna")
    2. Matcha extraherat namn fonetiskt mot registrerade deltagare
       → hanterar stavningsvarianter automatiskt
    """

    def __init__(self) -> None:
        self._active_speaker: str | None = None
        self._speaker_counter: int = 0
        # Registrerade deltagare: normalized_form → canonical_name
        # ex. "kendal" → "Kendal", "filip" → "Filip"
        self._participants: dict[str, str] = {}
        # Kända namn (ej registrerade): lowercase → canonical
        self._known_names: dict[str, str] = {}

    def set_participants(self, names: list[str]) -> None:
        """
        Registrera deltagare. Normaliserar varje namn för fonetisk matchning.
        Kortare fraser räcker sedan: "Kendal här", "det är Sara" etc.
        """
        self._participants = {}
        for name in names:
            if not name or not name.strip():
                continue
            canonical = name.strip().capitalize()
            norm = _normalize_name(canonical)
            self._participants[norm] = canonical

        logger.info(
            f"SpeakerTracker: {len(self._participants)} deltagare, "
            f"normaliserade: {dict(list(self._participants.items())[:5])}"
        )

    def _try_participant_match(self, word: str) -> str | None:
        """
        Försöker matcha ett enskilt ord fonetiskt mot registrerade deltagare.
        Returnerar det canoniska (registrerade) namnet, eller None.
        """
        if not self._participants:
            return None
        for norm_canonical, canonical in self._participants.items():
            if _name_matches(word, canonical, norm_canonical):
                return canonical
        return None

    def _next_anonymous(self) -> str:
        self._speaker_counter += 1
        return f"Talare {self._speaker_counter}"

    def _resolve_unknown_name(self, raw_name: str) -> str:
        """För namn som inte finns i deltagarlistan – cacha och returnera."""
        key = raw_name.lower().strip()
        if key not in self._known_names:
            self._known_names[key] = raw_name.strip().capitalize()
        return self._known_names[key]

    def current_speaker(self) -> str:
        if self._active_speaker is None:
            self._active_speaker = self._next_anonymous()
        return self._active_speaker

    def process(self, text: str) -> tuple[str, str]:
        """
        Parsar text, identifierar talare och returnerar (rengjord_text, talarnamn).

        Ordning:
        1. Extrahera potentiellt namn ur strukturella fraser + fonetisk match
           mot registrerade deltagare (hanterar stavningsvarianter)
        2. Generiska start-mönster för okända namn ("Nu talar Björn")
        3. Avslutningsfraser ("Klart slut")
        """
        cleaned = text
        speaker_event = None

        # --- Steg 1: Deltagarbaserad fonetisk matchning ---
        # Prova varje extraktionsmönster, hitta potentiellt namn, matcha fonetiskt.
        # Vi tar bort BARA den specifika matchade frasen (count=1) för att inte
        # råka ta bort exv "vara här" i "...det är kul att vara här" om vi
        # redan matchat "Kendal här" i början av chunken.
        for extractor in _NAME_EXTRACTORS:
            m = extractor.search(cleaned)
            if not m:
                continue
            candidate = m.group(1)
            canonical = self._try_participant_match(candidate)
            if canonical:
                speaker_event = ("start", canonical)
                # Ta bort EXAKT den matchade frasen (start/end position)
                cleaned = (cleaned[:m.start()] + cleaned[m.end():]).strip(" ,.-")
                logger.debug(
                    f"Fonetisk match: '{candidate}' → '{canonical}' "
                    f"(norm: {_normalize_name(candidate)} ≈ {_normalize_name(canonical)})"
                )
                break

        # --- Steg 2: Generiska start-mönster (okända namn) ---
        if speaker_event is None:
            for pattern in _START_PATTERNS:
                m = pattern.search(cleaned)
                if m:
                    raw = m.group(1)
                    # Kolla ändå om det fonetiskt matchar en deltagare
                    canonical = self._try_participant_match(raw)
                    name = canonical if canonical else self._resolve_unknown_name(raw)
                    speaker_event = ("start", name)
                    cleaned = (cleaned[:m.start()] + cleaned[m.end():]).strip(" ,.-")
                    break

        # --- Steg 3: Avslutningsfraser ---
        for pattern in _END_PATTERNS:
            m = pattern.search(cleaned)
            if m:
                if speaker_event is None:
                    speaker_event = ("end", None)
                cleaned = (cleaned[:m.start()] + cleaned[m.end():]).strip(" ,.-")
                break

        # --- Uppdatera state ---
        if speaker_event:
            kind, name = speaker_event
            if kind == "start":
                self._active_speaker = name
                logger.info(f"Talarbyte: '{name}' börjar tala")
            elif kind == "end":
                logger.info(f"Talarbyte: '{self._active_speaker}' avslutar")
                self._active_speaker = None

        return cleaned, self.current_speaker()


# ---------------------------------------------------------------------------
# Modell-singleton och hjälpfunktioner
# ---------------------------------------------------------------------------

# Modellen cachas globalt – delas mellan alla WebSocket-sessioner
_cached_model = None
_cached_processor = None


def _get_model():
    """Ladda KB-Whisper en gång och cacha för alla live-sessioner."""
    global _cached_model, _cached_processor
    if _cached_model is not None:
        return _cached_model, _cached_processor

    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Ladda explicit i float16 på GPU (som easytranscriber gör) – undviker dtype-mismatch
    dtype = torch.float16 if device == "cuda" else torch.float32

    logger.info(f"Laddar live-modell: {settings.transcription_model} ({dtype} på {device})")
    _cached_processor = WhisperProcessor.from_pretrained(
        settings.transcription_model,
        cache_dir=str(settings.models_cache_dir),
    )
    _cached_model = WhisperForConditionalGeneration.from_pretrained(
        settings.transcription_model,
        torch_dtype=dtype,
        cache_dir=str(settings.models_cache_dir),
    ).to(device)
    _cached_model.eval()
    logger.info(f"Live-modell redo: {settings.transcription_model} på {device}")
    return _cached_model, _cached_processor


def preload_model() -> None:
    """Anropas vid startup för att värma upp modellen innan första WebSocket-anslutning."""
    _get_model()
    logger.info("Live-modell förladdad och redo")


def _get_ffmpeg_exe() -> str:
    """
    Hittar ffmpeg-binären. Försöker imageio_ffmpeg (bundlad) först,
    faller tillbaka på system-PATH.
    """
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    return "ffmpeg"


def _decode_audio(audio_bytes: bytes) -> tuple[np.ndarray, float]:
    """
    Konverterar godtyckligt audioformat (WebM, Opus, MP4, WAV…) till
    16kHz mono float32 NumPy-array via ffmpeg pipe.
    Använder imageio_ffmpeg (bundlad binär) för att undvika PATH-beroenden på Windows.
    Returnerar (audio_array, duration_seconds).
    """
    ffmpeg = _get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-i", "pipe:0",   # läs från stdin
        "-ar", "16000",    # resampla till 16kHz
        "-ac", "1",        # mono
        "-f", "f32le",     # 32-bit float PCM little-endian
        "pipe:1",          # skriv PCM-data till stdout
    ]
    result = subprocess.run(
        cmd,
        input=audio_bytes,
        capture_output=True,
    )
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace")
        raise RuntimeError(f"ffmpeg avkodning misslyckades: {err}")

    audio_array = np.frombuffer(result.stdout, dtype=np.float32).copy()
    if audio_array.size == 0:
        raise RuntimeError("ffmpeg producerade tom output – chunken är för kort eller tom")

    duration = len(audio_array) / 16000.0
    return audio_array, duration


class LiveTranscriptionAdapter:
    """En instans per WebSocket-session. Modellen delas globalt."""

    def __init__(self) -> None:
        self._chunk_start = 0.0
        self._speaker_tracker = SpeakerTracker()

    def set_participants(self, names: list[str]) -> None:
        """Registrera deltagarnamn – anropas från WebSocket-routen vid init-meddelande."""
        self._speaker_tracker.set_participants(names)

    async def transcribe_chunk(self, audio_bytes: bytes, chunk_index: int) -> dict:
        """Transkriberar en audio-chunk asynkront (blockerar inte event loop)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._transcribe_sync, audio_bytes, chunk_index
        )

    def _transcribe_sync(self, audio_bytes: bytes, chunk_index: int) -> dict:
        model, processor = _get_model()

        # Steg 1: avkoda bytes → 16kHz mono float32
        try:
            audio_array, chunk_duration = _decode_audio(audio_bytes)
        except RuntimeError as exc:
            logger.error(f"Audio-avkodning misslyckades för chunk #{chunk_index}: {exc}")
            return {"error": str(exc), "chunk": chunk_index}

        chunk_start = self._chunk_start
        self._chunk_start += chunk_duration

        # Steg 2: tystnadsdetektion via RMS
        # Whisper hallucinerar fraser ("Tack.", "Varsågod.") på tyst audio.
        # RMS för normaliserat float32 audio: tyst < 0.01, tal > 0.02–0.10
        rms = float(np.sqrt(np.mean(audio_array ** 2)))
        silence_threshold = 0.01  # Justerbar – höj om hallucination kvarstår

        if rms < silence_threshold:
            logger.debug(
                f"Chunk #{chunk_index} ({chunk_duration:.1f}s): tyst (RMS={rms:.4f}) – hoppar över"
            )
            return {
                "chunk": chunk_index,
                "start": round(chunk_start, 2),
                "end": round(chunk_start + chunk_duration, 2),
                "text": "",
                "speaker": "Talare 1",
                "silent": True,
            }

        # Steg 3: feature extraction + inferens
        device = next(model.parameters()).device
        dtype = next(model.parameters()).dtype  # float16 på GPU (laddad explicit)

        inputs = processor(
            audio_array,
            sampling_rate=16000,
            return_tensors="pt",
        ).input_features.to(device=device, dtype=dtype)

        with torch.no_grad():
            predicted_ids = model.generate(
                inputs,
                language="sv",
                task="transcribe",
            )

        raw_text = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()
        logger.debug(f"Chunk #{chunk_index} ({chunk_duration:.1f}s) RMS={rms:.4f}: '{raw_text[:60]}'")

        # Parsa nyckelord och identifiera talare
        text, speaker = self._speaker_tracker.process(raw_text)

        return {
            "chunk": chunk_index,
            "start": round(chunk_start, 2),
            "end": round(chunk_start + chunk_duration, 2),
            "text": text,
            "speaker": speaker,
        }

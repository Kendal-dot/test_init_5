# Transkriberingspipeline

## Översikt

Systemet använder **KB-Whisper** via **easytranscriber** för transkribering och
**pyannote.audio** för talaridentifiering (diarization).

```
Uppladdad fil
     │
     ▼
ffmpeg konvertering
(video/audio → WAV 16kHz mono)
     │
     ├──────────────────────────────┐
     ▼                              ▼
easytranscriber pipeline        pyannote diarization
  1. VAD (Silero/Pyannote)       (om aktiverat)
  2. KB-Whisper transkribering   → {start, end, speaker_id}
  3. Emission extraction
  4. Forced alignment (GPU)
     │                              │
     ▼                              ▼
  text + timestamps          speaker → "Talare 1"
     │                              │
     └──────────────┬───────────────┘
                    ▼
             Merge-steg
             Matcha diarization-segment
             mot transkript-segment via
             tidsöverlapp
                    │
                    ▼
             Spara i SQLite
             {start, end, speaker, text}
```

---

## Varför KB-Whisper?

KB-Whisper är KBLabs fintrände Whisper-varianter för svenska, tränade på >50.000h
transiberat svenskt tal (TV-undertexter, riksdagsprotokoll, dialektarkiv, YouTube).

| Modell | WER (FLEURS) | vs OpenAI large-v3 |
|--------|-------------|-------------------|
| kb-whisper-small | 7.3% | -65% |
| kb-whisper-medium | 6.6% | -45% |
| kb-whisper-large | 5.4% | -31% |

`kb-whisper-small` rekommenderas för MVP – det slår OpenAI:s `whisper-large-v3`
trots att det är 6× mindre (0.3B vs 1.5B parametrar).

---

## Varför easytranscriber?

easytranscriber är KBLabs eget ASR-bibliotek som:
- Ger **GPU-accelererad forced alignment** (word-level timestamps)
- Är **35–102% snabbare** än WhisperX
- Stödjer ctranslate2 (produktionsrekommenderat) och HF transformers
- Har inbyggd pipeline: VAD → transkribering → emission → alignment

---

## Varför Silero VAD som default?

Silero VAD används för Voice Activity Detection (identifiera talsegment i audio).
Fördel jämfört med pyannote VAD:
- **Kräver ingen HuggingFace-autentisering** (inga gated models)
- Enklare setup för lokal körning
- Bra kvalitet för svenska möten

Byt till pyannote VAD i `.env` om du vill ha mer exakt VAD:
```
VAD_BACKEND=pyannote
HF_TOKEN=hf_xxx...
```

---

## Talaridentifiering (Diarization)

pyannote.audio `speaker-diarization-3.1` används för att identifiera vem som talar.

**Merge-algoritm:**
1. easytranscriber ger segment med start/end-tider
2. pyannote ger diarization-segment med speaker_id
3. För varje transkriptsegment: hitta det diarization-segment med störst tidsöverlapp
4. Tilldela talaretikett baserat på överlapp

Talare namnges generiskt: "Talare 1", "Talare 2", etc.
Ordning baseras på första förekomst i tid.

**Utan diarization:** Alla segment sparas utan talaretikett.

---

## Live-transkribering

Live-läget använder en förenklad pipeline:
- Ingen forced alignment (för långsam för realtid)
- Direkt KB-Whisper inferens per chunk
- Chunks skickas som WAV-bytes via WebSocket
- Latens: 5–15s per chunk på GPU

```
Mikrofon
  │  10s chunk
  ▼
MediaRecorder (WebM)
  │
  ▼ WebSocket
Backend
  │
  ▼
KB-Whisper (direkt, ingen alignment)
  │
  ▼ WebSocket JSON
Frontend
```

---

## Wav2vec2 emission-modell för svenska

För forced alignment används `KBLab/wav2vec2-large-voxrex-swedish` –
KBLabs svenska wav2vec2-modell tränad på riksdagsprotokoll och annat.

---

## Kända begränsningar

- Forced alignment kan misslyckas för ovanliga ord och dialekter
- Live-transkribering har ingen cross-chunk kontext → sämre vid avskurna meningar
- Diarization fungerar bäst med tydligt separerade talare och lite bakgrundsbuller
- Stora filer (>2h) kan kräva mer minne under pipeline-körning

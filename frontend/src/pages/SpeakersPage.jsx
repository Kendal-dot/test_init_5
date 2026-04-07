import { useState, useRef, useEffect } from 'react'
import { useSpeakers } from '../hooks/useSpeakers'
import { enrollSpeaker } from '../services/api'
import { formatDate } from '../utils/format'

const ENROLLMENT_TEXT = `Välkommen till röstprofilregistrering. Läs denna text högt i lugn takt med din normala röst.

Sverige är ett land i norra Europa. Landet har en lång historia av innovation och samarbete. Under de senaste åren har digitaliseringen förändrat hur vi arbetar och kommunicerar.

Möten är en viktig del av arbetslivet. Varje dag hålls tusentals möten där viktiga beslut fattas, idéer diskuteras och projekt planeras framåt. Bra kommunikation kräver att alla kan göra sig hörda.

Transkribering av möten sparar tid och säkerställer att inget viktigt missas. Genom att automatiskt omvandla tal till text kan vi fokusera på samtalet istället för att anteckna.`

function getSupportedMimeType() {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ]
  for (const mime of candidates) {
    if (MediaRecorder.isTypeSupported(mime)) return mime
  }
  return ''
}

export default function SpeakersPage() {
  const { speakers, loading, error: listError, refetch, removeSpeaker } = useSpeakers()
  const [name, setName] = useState('')
  const [recording, setRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const [audioBlob, setAudioBlob] = useState(null)
  const [enrolling, setEnrolling] = useState(false)
  const [enrollError, setEnrollError] = useState(null)
  const [enrollSuccess, setEnrollSuccess] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const timerRef = useRef(null)

  useEffect(() => {
    return () => {
      clearInterval(timerRef.current)
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const startRecording = async () => {
    setEnrollError(null)
    setEnrollSuccess(null)
    setAudioBlob(null)
    setRecordingTime(0)
    chunksRef.current = []

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const mimeType = getSupportedMimeType()
      const options = mimeType ? { mimeType } : {}
      const recorder = new MediaRecorder(stream, options)
      recorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType })
        setAudioBlob(blob)
        stream.getTracks().forEach((t) => t.stop())
        clearInterval(timerRef.current)
      }

      recorder.start(1000)
      setRecording(true)

      const startTime = Date.now()
      timerRef.current = setInterval(() => {
        setRecordingTime(Math.floor((Date.now() - startTime) / 1000))
      }, 500)
    } catch (err) {
      setEnrollError(`Mikrofonåtkomst nekades: ${err.message}`)
    }
  }

  const stopRecording = () => {
    if (recorderRef.current && recorderRef.current.state === 'recording') {
      recorderRef.current.stop()
    }
    setRecording(false)
    clearInterval(timerRef.current)
  }

  const handleEnroll = async () => {
    if (!name.trim() || !audioBlob) return
    setEnrolling(true)
    setEnrollError(null)

    try {
      await enrollSpeaker(name.trim(), audioBlob)
      setEnrollSuccess(`Röstprofil för "${name.trim()}" har sparats!`)
      setName('')
      setAudioBlob(null)
      setRecordingTime(0)
      refetch()
    } catch (err) {
      setEnrollError(err.response?.data?.detail || 'Kunde inte spara röstprofilen')
    } finally {
      setEnrolling(false)
    }
  }

  const handleDelete = async (id, speakerName) => {
    if (!confirm(`Ta bort röstprofilen för "${speakerName}"?`)) return
    setDeleting(id)
    await removeSpeaker(id)
    setDeleting(null)
  }

  const formatSeconds = (s) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${String(sec).padStart(2, '0')}`
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Röstprofiler</h1>
        <p className="page-subtitle">
          Registrera din röst så att systemet kan identifiera dig automatiskt vid transkribering
        </p>
      </div>

      {/* Registreringsformulär */}
      <div className="card enroll-card">
        <h3>Registrera ny röstprofil</h3>

        <div className="enroll-name-row">
          <label className="enroll-label">Ditt namn</label>
          <input
            className="search-input"
            type="text"
            placeholder="Skriv ditt namn"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={recording || enrolling}
          />
        </div>

        <div className="enroll-text-card">
          <h4>Läs följande text högt:</h4>
          <p className="enroll-text">{ENROLLMENT_TEXT}</p>
        </div>

        <div className="enroll-controls">
          {!recording && !audioBlob && (
            <button
              className="btn btn-primary btn-large"
              onClick={startRecording}
              disabled={!name.trim() || enrolling}
            >
              Starta inspelning
            </button>
          )}

          {recording && (
            <div className="enroll-recording">
              <div className="enroll-recording-status">
                <span className="live-indicator active" />
                <span>Spelar in... {formatSeconds(recordingTime)}</span>
                {recordingTime < 10 && (
                  <span className="hint-small">(minst 10 sekunder)</span>
                )}
              </div>
              <button
                className="btn btn-danger btn-large"
                onClick={stopRecording}
                disabled={recordingTime < 5}
              >
                Stoppa inspelning
              </button>
            </div>
          )}

          {audioBlob && !recording && (
            <div className="enroll-review">
              <div className="enroll-review-info">
                <span className="status-badge status-completed">
                  Inspelning klar – {formatSeconds(recordingTime)}
                </span>
              </div>
              <div className="enroll-review-actions">
                <button
                  className="btn btn-primary"
                  onClick={handleEnroll}
                  disabled={enrolling}
                >
                  {enrolling ? 'Sparar profil...' : 'Spara röstprofil'}
                </button>
                <button
                  className="btn"
                  onClick={startRecording}
                  disabled={enrolling}
                >
                  Spela in igen
                </button>
              </div>
            </div>
          )}
        </div>

        {enrollError && <p className="error-msg">{enrollError}</p>}
        {enrollSuccess && (
          <p className="success-msg">{enrollSuccess}</p>
        )}

        <div className="enroll-info">
          <p className="hint-small">
            Minst 10 sekunder krävs, men 30-60 sekunder ger bäst resultat.
            Prata med din normala röst. Profilen används för att identifiera dig automatiskt
            vid framtida mötestranskriberingar.
          </p>
        </div>
      </div>

      {/* Lista registrerade profiler */}
      <div className="card">
        <h3>Registrerade röstprofiler</h3>

        {loading && <div className="loading">Laddar...</div>}
        {listError && <div className="error-msg">{listError}</div>}

        {!loading && speakers.length === 0 ? (
          <div className="empty-state">
            Inga röstprofiler registrerade ännu. Registrera din röst ovan för att komma igång.
          </div>
        ) : (
          <div className="speakers-list">
            {speakers.map((speaker) => (
              <div key={speaker.id} className="speaker-item">
                <div className="speaker-item-info">
                  <span className="speaker-item-name">{speaker.name}</span>
                  <span className="speaker-item-meta">
                    {speaker.audio_duration
                      ? `${Math.round(speaker.audio_duration)}s inspelning`
                      : ''
                    }
                    {' · '}
                    Registrerad {formatDate(speaker.created_at)}
                  </span>
                </div>
                <button
                  className="btn btn-sm btn-danger"
                  onClick={() => handleDelete(speaker.id, speaker.name)}
                  disabled={deleting === speaker.id}
                >
                  {deleting === speaker.id ? 'Tar bort...' : 'Ta bort'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card info-card">
        <h3>Hur fungerar det?</h3>
        <ul>
          <li>Din röst omvandlas till ett <strong>röstfingeravtryck</strong> (192 tal) med AI-modellen ECAPA-TDNN</li>
          <li>Fingeravtrycket sparas <strong>lokalt</strong> i databasen – ingen data skickas ut</li>
          <li>Vid transkribering jämförs varje talares röst mot sparade profiler</li>
          <li>Om en match hittas visas ditt <strong>riktiga namn</strong> istället för "Talare 1"</li>
          <li>30-60 sekunders inspelning räcker för tillförlitlig identifiering</li>
        </ul>
      </div>
    </div>
  )
}

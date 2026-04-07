import { useRef, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLiveTranscription } from '../hooks/useLiveTranscription'
import { saveLiveSession } from '../services/api'
import { formatTime } from '../utils/format'

const STATUS_LABELS = {
  idle: 'Stoppad',
  connecting: 'Ansluter...',
  recording: 'Spelar in',
  stopping: 'Stoppar...',
  error: 'Fel',
}

const SPEAKER_COLORS = [
  '#2563eb', '#16a34a', '#dc2626', '#d97706',
  '#7c3aed', '#0891b2', '#be185d', '#65a30d',
]

function speakerColor(label) {
  if (!label) return '#6b7280'
  // Namnbaserad färg – konsekvent för samma namn oavsett ordning
  let hash = 0
  for (const c of label) hash = (hash * 31 + c.charCodeAt(0)) & 0xffff
  return SPEAKER_COLORS[hash % SPEAKER_COLORS.length]
}

export default function LivePage() {
  const [participants, setParticipants] = useState([])
  const [nameInput, setNameInput] = useState('')
  const [meetingTitle, setMeetingTitle] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const { blocks, status, error, processing, start, stop } = useLiveTranscription(participants)
  const bottomRef = useRef(null)
  const navigate = useNavigate()
  const isRecording = status === 'recording'
  const isStopped = status === 'idle' && blocks.length > 0

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [blocks, processing])

  const addParticipant = () => {
    const name = nameInput.trim()
    if (!name || participants.includes(name)) return
    setParticipants((prev) => [...prev, name])
    setNameInput('')
  }

  const removeParticipant = (name) =>
    setParticipants((prev) => prev.filter((n) => n !== name))

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') addParticipant()
  }

  const handleSave = async () => {
    if (blocks.length === 0) return
    setSaving(true)
    setSaveError(null)
    try {
      const res = await saveLiveSession(meetingTitle, participants, blocks)
      navigate(`/transcript/${res.data.id}`)
    } catch (err) {
      setSaveError(err.response?.data?.detail || 'Kunde inte spara mötet')
      setSaving(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Live-transkribering</h1>
        <p className="page-subtitle">
          Transkriberar via mikrofon med KB-Whisper lokalt – ~3–5s latens
        </p>
      </div>

      {/* Deltagarformulär – visas bara innan inspelning */}
      {!isRecording && (
        <div className="card participants-card">
          <h3>Mötesdeltagare <span className="hint-small">(valfritt men rekommenderat)</span></h3>
          <p className="hint-small" style={{ marginBottom: '.75rem' }}>
            Lägg till namn så räcker det att säga <em>"Kendal här"</em> för att identifiera talaren.
            Utan namn krävs <em>"Nu talar Kendal"</em>.
          </p>

          <div className="participant-input-row">
            <input
              className="search-input"
              type="text"
              placeholder="Skriv ett namn och tryck Enter"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isRecording}
            />
            <button className="btn btn-primary" onClick={addParticipant} disabled={!nameInput.trim()}>
              Lägg till
            </button>
          </div>

          {participants.length > 0 && (
            <div className="participant-chips">
              {participants.map((name) => (
                <span key={name} className="participant-chip">
                  <span
                    className="participant-chip-dot"
                    style={{ background: speakerColor(name) }}
                  />
                  {name}
                  <button
                    className="participant-chip-remove"
                    onClick={() => removeParticipant(name)}
                    title="Ta bort"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="card live-controls">
        <div className="live-status">
          <span className={`live-indicator ${isRecording ? 'active' : ''}`} />
          <span>{STATUS_LABELS[status]}</span>
          {isRecording && processing && (
            <span className="processing-badge">Lyssnar...</span>
          )}
        </div>

        {!isRecording ? (
          <button
            className="btn btn-primary btn-large"
            onClick={start}
            disabled={status === 'connecting' || status === 'stopping'}
          >
            {status === 'connecting' ? 'Ansluter...' : 'Starta inspelning'}
          </button>
        ) : (
          <button className="btn btn-danger btn-large" onClick={stop}>
            Stoppa
          </button>
        )}

        <p className="hint-small">
          {participants.length > 0
            ? `${participants.length} deltagare registrerade – säg ex. "${participants[0]} här" för att identifiera dig`
            : 'Säg "Nu talar [namn]" för att identifiera talaren, "Klart slut" för att avsluta.'}
        </p>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* Spara-sektion – visas efter att inspelningen stoppats */}
      {isStopped && (
        <div className="card save-session-card">
          <h3>Spara mötet</h3>
          <div className="save-session-row">
            <input
              className="search-input"
              type="text"
              placeholder={`Mötesnamn (valfritt, ex. "Teammöte ${new Date().toLocaleDateString('sv-SE')}")`}
              value={meetingTitle}
              onChange={(e) => setMeetingTitle(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSave()}
            />
            <button
              className="btn btn-primary"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? 'Sparar...' : 'Spara & visa transkript'}
            </button>
          </div>
          {saveError && <p className="error-msg" style={{ marginTop: '.5rem' }}>{saveError}</p>}
          <p className="hint-small">
            {blocks.length} block · {blocks.reduce((n, b) => n + b.text.split(' ').length, 0)} ord
          </p>
        </div>
      )}

      <div className="live-transcript-area">
        {blocks.length === 0 && !processing ? (
          <div className="card">
            <div className="empty-state">
              {isRecording
                ? 'Börja prata – text dyker upp om ~3 sekunder'
                : 'Klicka "Starta inspelning" och börja prata.'}
            </div>
          </div>
        ) : (
          <>
            {blocks.map((block) => (
              <div key={block.id} className="live-block">
                <div className="live-block-meta">
                  <span
                    className="live-block-speaker"
                    style={{ borderLeftColor: speakerColor(block.speaker) }}
                  >
                    {block.speaker}
                  </span>
                  <span className="live-block-time">
                    {formatTime(block.start)}
                    {block.end > block.start && ` – ${formatTime(block.end)}`}
                  </span>
                </div>
                <p className="live-block-text">{block.text}</p>
              </div>
            ))}

            {processing && (
              <div className="live-block live-block-pending">
                <div className="live-block-meta">
                  <span className="live-block-speaker" style={{ borderLeftColor: '#94a3b8' }}>
                    ...
                  </span>
                </div>
                <p className="live-block-text-pending">▌</p>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

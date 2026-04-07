import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useTranscript } from '../hooks/useTranscript'
import { useJob } from '../hooks/useJobs'
import { exportTranscriptTxt, exportTranscriptJson } from '../services/api'
import { formatTime } from '../utils/format'

const SPEAKER_COLORS = [
  '#2563eb', '#16a34a', '#dc2626', '#d97706',
  '#7c3aed', '#0891b2', '#be185d', '#65a30d',
]

function speakerColor(label) {
  if (!label) return '#6b7280'
  const num = parseInt(label.replace(/\D/g, ''), 10) || 1
  return SPEAKER_COLORS[(num - 1) % SPEAKER_COLORS.length]
}

function SegmentRow({ segment, onSave, onRestore, saving }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(segment.text)

  const handleSave = async () => {
    if (text.trim() === segment.text) {
      setEditing(false)
      return
    }
    await onSave(segment.id, text.trim())
    setEditing(false)
  }

  const handleRestore = async () => {
    await onRestore(segment.id)
    setText(segment.original_text)
  }

  return (
    <div className={`segment-row ${segment.is_edited ? 'edited' : ''}`}>
      <div className="segment-meta">
        <span
          className="speaker-label"
          style={{ borderColor: speakerColor(segment.speaker_label) }}
        >
          {segment.speaker_label || 'Okänd'}
        </span>
        <span className="timestamp">
          {formatTime(segment.start_time)} – {formatTime(segment.end_time)}
        </span>
        {segment.is_edited && <span className="edited-badge">Redigerad</span>}
      </div>

      {editing ? (
        <div className="segment-edit">
          <textarea
            className="segment-textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={Math.max(2, Math.ceil(text.length / 80))}
            autoFocus
          />
          <div className="segment-edit-actions">
            <button className="btn btn-sm btn-primary" onClick={handleSave} disabled={saving}>
              Spara
            </button>
            <button className="btn btn-sm" onClick={() => { setEditing(false); setText(segment.text) }}>
              Avbryt
            </button>
          </div>
        </div>
      ) : (
        <div className="segment-text-wrap">
          <p className="segment-text">{segment.text}</p>
          <div className="segment-actions">
            <button className="btn-icon" title="Redigera" onClick={() => setEditing(true)}>
              ✏️
            </button>
            {segment.is_edited && (
              <button className="btn-icon" title="Återställ original" onClick={handleRestore} disabled={saving}>
                ↺
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function TranscriptPage() {
  const { meetingId } = useParams()
  const { transcript, loading, error, saving, saveSegment, restoreSegmentText } = useTranscript(meetingId)
  const { job } = useJob(meetingId, 0)
  const [filterSpeaker, setFilterSpeaker] = useState('all')

  if (loading) return <div className="page"><div className="loading">Laddar transkript...</div></div>
  if (error) return <div className="page"><div className="error-msg">{error}</div></div>
  if (!transcript) return null

  const speakers = [...new Set(transcript.segments.map(s => s.speaker_label).filter(Boolean))]
  const filtered = filterSpeaker === 'all'
    ? transcript.segments
    : transcript.segments.filter(s => s.speaker_label === filterSpeaker)

  return (
    <div className="page">
      <div className="page-header">
        <div className="breadcrumb">
          <Link to="/jobs">← Jobb</Link>
        </div>
        <h1>{job?.original_filename || 'Transkript'}</h1>
        <p className="page-subtitle">
          {transcript.segments.length} segment
          {speakers.length > 0 && ` · ${speakers.length} talare`}
        </p>
      </div>

      <div className="transcript-toolbar">
        <div className="speaker-filter">
          <button
            className={`filter-btn ${filterSpeaker === 'all' ? 'active' : ''}`}
            onClick={() => setFilterSpeaker('all')}
          >
            Alla
          </button>
          {speakers.map(sp => (
            <button
              key={sp}
              className={`filter-btn ${filterSpeaker === sp ? 'active' : ''}`}
              style={{ borderColor: speakerColor(sp) }}
              onClick={() => setFilterSpeaker(sp === filterSpeaker ? 'all' : sp)}
            >
              {sp}
            </button>
          ))}
        </div>

        <div className="export-buttons">
          <button
            className="btn btn-secondary"
            onClick={() => exportTranscriptTxt(meetingId)}
          >
            Exportera TXT
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => exportTranscriptJson(meetingId)}
          >
            Exportera JSON
          </button>
        </div>
      </div>

      <div className="transcript-container">
        {filtered.length === 0 ? (
          <div className="empty-state">Inga segment att visa.</div>
        ) : (
          filtered.map((seg) => (
            <SegmentRow
              key={seg.id}
              segment={seg}
              onSave={saveSegment}
              onRestore={restoreSegmentText}
              saving={saving}
            />
          ))
        )}
      </div>
    </div>
  )
}

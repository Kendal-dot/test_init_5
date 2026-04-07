import { useState } from 'react'
import { Link } from 'react-router-dom'
import { searchTranscripts } from '../services/api'
import { formatTime } from '../utils/format'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSearch = async (e) => {
    e.preventDefault()
    if (query.trim().length < 2) return
    setLoading(true)
    setError(null)
    try {
      const res = await searchTranscripts(query)
      setResults(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  const highlight = (text, q) => {
    if (!q) return text
    const parts = text.split(new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'))
    return parts.map((part, i) =>
      part.toLowerCase() === q.toLowerCase()
        ? <mark key={i}>{part}</mark>
        : part
    )
  }

  // Gruppera resultat per möte
  const grouped = results
    ? results.reduce((acc, r) => {
        if (!acc[r.meeting_id]) acc[r.meeting_id] = []
        acc[r.meeting_id].push(r)
        return acc
      }, {})
    : {}

  return (
    <div className="page">
      <div className="page-header">
        <h1>Sök i transkript</h1>
      </div>

      <form className="search-form" onSubmit={handleSearch}>
        <input
          className="search-input"
          type="text"
          placeholder="Sök i alla transkript..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          minLength={2}
          autoFocus
        />
        <button
          className="btn btn-primary"
          type="submit"
          disabled={loading || query.trim().length < 2}
        >
          {loading ? 'Söker...' : 'Sök'}
        </button>
      </form>

      {error && <div className="error-msg">{error}</div>}

      {results !== null && (
        <div className="search-results">
          <p className="results-count">
            {results.length} träff{results.length !== 1 ? 'ar' : ''} i {Object.keys(grouped).length} möte{Object.keys(grouped).length !== 1 ? 'n' : ''}
          </p>

          {results.length === 0 ? (
            <div className="empty-state">Inga träffar för <em>"{query}"</em></div>
          ) : (
            Object.entries(grouped).map(([meetingId, segs]) => (
              <div key={meetingId} className="card search-group">
                <div className="search-group-header">
                  <Link to={`/transcript/${meetingId}`} className="search-meeting-link">
                    Möte: {meetingId.slice(0, 8)}...
                  </Link>
                  <span className="count-badge">{segs.length} träffar</span>
                </div>
                {segs.map((seg) => (
                  <div key={seg.id} className="search-result-item">
                    <div className="search-result-meta">
                      {seg.speaker_label && (
                        <span className="speaker-label-sm">{seg.speaker_label}</span>
                      )}
                      <span className="timestamp">{formatTime(seg.start_time)}</span>
                    </div>
                    <p className="search-result-text">
                      {highlight(seg.text, query)}
                    </p>
                    <Link
                      to={`/transcript/${meetingId}`}
                      className="btn btn-sm"
                    >
                      Gå till transkript
                    </Link>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

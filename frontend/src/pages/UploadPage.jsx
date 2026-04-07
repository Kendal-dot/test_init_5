import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadFile } from '../services/api'
import { formatBytes } from '../utils/format'

const ACCEPTED_TYPES = '.mp3,.mp4,.wav,.m4a,.ogg,.flac,.webm,.mkv,.mov,.aac,.wma'

export default function UploadPage() {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  const handleFile = (f) => {
    setFile(f)
    setError(null)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const res = await uploadFile(file, setProgress)
      navigate(`/jobs/${res.data.id}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Uppladdning misslyckades')
      setUploading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Ladda upp mötesinspelning</h1>
        <p className="page-subtitle">
          Stöder MP3, MP4, WAV, M4A, OGG, FLAC, WEBM med flera
        </p>
      </div>

      <div className="card upload-card">
        <form onSubmit={handleSubmit}>
          <div
            className={`drop-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED_TYPES}
              style={{ display: 'none' }}
              onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])}
            />

            {file ? (
              <div className="file-info">
                <span className="file-icon">🎵</span>
                <div>
                  <div className="file-name">{file.name}</div>
                  <div className="file-size">{formatBytes(file.size)}</div>
                </div>
                <button
                  type="button"
                  className="btn-icon"
                  onClick={(e) => { e.stopPropagation(); setFile(null) }}
                >
                  ✕
                </button>
              </div>
            ) : (
              <div className="drop-zone-hint">
                <span className="drop-icon">📂</span>
                <p>Dra och släpp en fil här, eller klicka för att välja</p>
                <p className="hint-small">MP3, MP4, WAV, M4A, OGG, FLAC, WEBM, MKV, MOV</p>
              </div>
            )}
          </div>

          {uploading && (
            <div className="progress-bar-wrap">
              <div className="progress-bar" style={{ width: `${progress}%` }} />
              <span>{progress}%</span>
            </div>
          )}

          {error && <p className="error-msg">{error}</p>}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={!file || uploading}
          >
            {uploading ? 'Laddar upp...' : 'Starta transkribering'}
          </button>
        </form>
      </div>

      <div className="card info-card">
        <h3>Om transkriberingen</h3>
        <ul>
          <li>Modell: <strong>KB-Whisper</strong> – optimerad för svenska</li>
          <li>Talaridentifiering: <strong>Talare 1, Talare 2, ...</strong></li>
          <li>All bearbetning sker <strong>lokalt</strong> – inga data skickas ut</li>
          <li>Transkribering av 1h möte tar ca 5–15 minuter (GPU)</li>
        </ul>
      </div>
    </div>
  )
}

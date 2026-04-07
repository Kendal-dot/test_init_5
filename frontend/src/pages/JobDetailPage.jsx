import { useParams, Link } from 'react-router-dom'
import { useJob } from '../hooks/useJobs'
import StatusBadge from '../components/StatusBadge'
import { formatDate, formatBytes, formatTime } from '../utils/format'

export default function JobDetailPage() {
  const { meetingId } = useParams()
  const { job, loading, error } = useJob(meetingId)

  if (loading) return <div className="page"><div className="loading">Laddar...</div></div>
  if (error) return <div className="page"><div className="error-msg">{error}</div></div>
  if (!job) return null

  const isActive = job.status === 'queued' || job.status === 'processing'

  return (
    <div className="page">
      <div className="page-header">
        <div className="breadcrumb">
          <Link to="/jobs">← Jobb</Link>
        </div>
        <h1>{job.original_filename}</h1>
        <StatusBadge status={job.status} />
      </div>

      <div className="card">
        <h3>Jobbdetaljer</h3>
        <dl className="detail-list">
          <dt>Jobb-ID</dt><dd><code>{job.id}</code></dd>
          <dt>Filnamn</dt><dd>{job.original_filename}</dd>
          <dt>Filstorlek</dt><dd>{formatBytes(job.file_size_bytes)}</dd>
          <dt>Status</dt><dd><StatusBadge status={job.status} /></dd>
          <dt>Skapad</dt><dd>{formatDate(job.created_at)}</dd>
          <dt>Uppdaterad</dt><dd>{formatDate(job.updated_at)}</dd>
          {job.duration && <><dt>Längd</dt><dd>{formatTime(job.duration)}</dd></>}
          {job.model_used && <><dt>Modell</dt><dd>{job.model_used}</dd></>}
          {job.pipeline_used && <><dt>Pipeline</dt><dd>{job.pipeline_used}</dd></>}
          <dt>Källa</dt><dd>{job.source_type === 'live' ? 'Live-inspelning' : 'Uppladdad fil'}</dd>
        </dl>
      </div>

      {isActive && (
        <div className="card status-card processing">
          <div className="spinner" />
          <p>
            {job.status === 'queued'
              ? 'Jobbet väntar i kön...'
              : 'Transkriberar med KB-Whisper...'}
          </p>
          <p className="hint-small">Sidan uppdateras automatiskt</p>
        </div>
      )}

      {job.status === 'failed' && job.error_message && (
        <div className="card error-card">
          <h3>Felmeddelande</h3>
          <pre>{job.error_message}</pre>
        </div>
      )}

      {job.status === 'completed' && (
        <div className="card-actions">
          <Link to={`/transcript/${job.id}`} className="btn btn-primary">
            Visa transkript
          </Link>
        </div>
      )}
    </div>
  )
}

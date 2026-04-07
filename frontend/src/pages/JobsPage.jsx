import { Link } from 'react-router-dom'
import { useJobs } from '../hooks/useJobs'
import StatusBadge from '../components/StatusBadge'
import { formatDate, formatBytes, formatTime } from '../utils/format'

export default function JobsPage() {
  const { jobs, total, loading, error } = useJobs(5000)

  if (loading) return <div className="page"><div className="loading">Laddar...</div></div>
  if (error) return <div className="page"><div className="error-msg">{error}</div></div>

  return (
    <div className="page">
      <div className="page-header">
        <h1>Transkriberingsjobb</h1>
        <span className="count-badge">{total} totalt</span>
      </div>

      {jobs.length === 0 ? (
        <div className="empty-state">
          <p>Inga jobb ännu. <Link to="/">Ladda upp en fil</Link> för att komma igång.</p>
        </div>
      ) : (
        <div className="jobs-list">
          {jobs.map((job) => (
            <div key={job.id} className="card job-card">
              <div className="job-card-header">
                <div className="job-filename">{job.original_filename}</div>
                <StatusBadge status={job.status} />
              </div>
              <div className="job-meta">
                <span>Skapad: {formatDate(job.created_at)}</span>
                {job.duration && <span>Längd: {formatTime(job.duration)}</span>}
                {job.file_size_bytes && <span>Storlek: {formatBytes(job.file_size_bytes)}</span>}
                {job.model_used && <span>Modell: {job.model_used}</span>}
              </div>
              {job.error_message && (
                <div className="job-error">{job.error_message}</div>
              )}
              <div className="job-actions">
                <Link to={`/jobs/${job.id}`} className="btn btn-sm">
                  Detaljer
                </Link>
                {job.status === 'completed' && (
                  <Link to={`/transcript/${job.id}`} className="btn btn-sm btn-primary">
                    Visa transkript
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

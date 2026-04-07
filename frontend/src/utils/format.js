/**
 * Formatera sekunder som MM:SS eller H:MM:SS
 */
export function formatTime(seconds) {
  if (seconds == null || isNaN(seconds)) return '--:--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/**
 * Formatera bytes som läsbar storlek
 */
export function formatBytes(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * Formatera ISO-datum som lokal tid
 */
export function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('sv-SE', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Statusetikett → färgklass
 */
export function statusColor(status) {
  switch (status) {
    case 'completed': return 'status-completed'
    case 'processing': return 'status-processing'
    case 'queued': return 'status-queued'
    case 'failed': return 'status-failed'
    default: return 'status-unknown'
  }
}

export function statusLabel(status) {
  switch (status) {
    case 'completed': return 'Klar'
    case 'processing': return 'Bearbetar'
    case 'queued': return 'I kö'
    case 'failed': return 'Misslyckad'
    default: return status
  }
}

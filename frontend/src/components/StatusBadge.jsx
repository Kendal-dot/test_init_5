import { statusColor, statusLabel } from '../utils/format'

export default function StatusBadge({ status }) {
  return (
    <span className={`status-badge ${statusColor(status)}`}>
      {statusLabel(status)}
    </span>
  )
}

import { RevenueAnomalyCard as RevenueAnomalyCardData } from '../../../services/ownerDashboard';

interface Props {
  card: RevenueAnomalyCardData;
  variant?: 'compact' | 'detail';
  isStale?: boolean;
  onDismiss?: () => void;
}

export default function RevenueAnomalyCard({ card, variant = 'detail', isStale = false, onDismiss }: Props) {
  const severityClass =
    card.severity === 'high' ? 'critical' :
    card.severity === 'low' ? 'info' : 'warning';

  const ageLabel = formatAge(card.created_at);

  if (variant === 'compact') {
    return (
      <div className={`board-card-compact board-card--${severityClass}${isStale ? ' board-card--stale' : ''}`}>
        <div className="board-card-name board-card-name--truncate">
          {card.message || 'Revenue anomaly detected'}
        </div>
        <span className={`board-card-pill pill--${isStale ? 'stale' : severityClass}`}>
          {isStale ? `⚠ ${ageLabel}` : ageLabel}
        </span>
      </div>
    );
  }

  return (
    <div className={`action-card action-card--${severityClass}`}>
      <div className="action-card-header">
        <span className={`action-card-badge badge--${severityClass}`}>Revenue alert</span>
        <span className="action-card-type-label">{isStale ? `Stale · ${ageLabel}` : ageLabel}</span>
      </div>
      <div className="action-card-title">{card.message || 'Revenue anomaly detected'}</div>
      <div className="action-card-meta">
        Severity: {card.severity} · Detected {formatFull(card.created_at)}
      </div>
      {isStale && (
        <div className="action-card-stale-note">
          This alert is from {ageLabel} and may no longer be relevant.
        </div>
      )}
      {onDismiss && (
        <div className="po-card-actions" style={{ marginTop: 8 }}>
          <button className="btn btn-sm btn-outline" onClick={onDismiss}>
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}

function formatAge(isoDate: string): string {
  if (!isoDate) return '';
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatFull(isoDate: string): string {
  if (!isoDate) return 'unknown';
  return new Date(isoDate).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

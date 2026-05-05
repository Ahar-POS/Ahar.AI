import { ChannelDipCard, OperationsAlertCard as OpsAlertData } from '../../../services/ownerDashboard';

// ── Channel Dip ───────────────────────────────────────────────────────────────

interface ChannelDipProps {
  card: ChannelDipCard;
  variant?: 'compact' | 'detail';
  onDismiss?: () => void;
}

export function ChannelDipCardComponent({ card, variant = 'detail', onDismiss }: ChannelDipProps) {
  const severityClass = card.severity === 'high' ? 'critical' : 'warning';
  const ageLabel = formatAge(card.created_at);
  const worstPct = Math.round((1 - card.worst_ratio) * 100);

  if (variant === 'compact') {
    return (
      <div className={`board-card-compact board-card--${severityClass}`}>
        <div className="board-card-name board-card-name--truncate">
          {card.channel_count} channel{card.channel_count > 1 ? 's' : ''} down — {worstPct}% below avg
        </div>
        <span className={`board-card-pill pill--${severityClass}`}>{ageLabel}</span>
      </div>
    );
  }

  return (
    <div className={`action-card action-card--${severityClass}`}>
      <div className="action-card-header">
        <span className={`action-card-badge badge--${severityClass}`}>Channel Dip</span>
        <span className="action-card-type-label">{ageLabel}</span>
      </div>
      <div className="action-card-title">
        {card.channel_count} channel{card.channel_count > 1 ? 's' : ''} underperforming at {card.hour}:00
      </div>
      <div className="action-card-meta" style={{ marginTop: 8 }}>
        {card.channels.map((c) => (
          <div key={c.channel} style={{ marginBottom: 4 }}>
            <strong>{c.channel.replace('_', '-')}</strong>
            {c.zero_orders
              ? ' — 0 orders'
              : ` — ₹${c.current_revenue_inr.toLocaleString('en-IN')} (${Math.round((1 - c.ratio) * 100)}% below avg, ${c.current_order_count} orders)`
            }
          </div>
        ))}
      </div>
      {onDismiss && (
        <div className="po-card-actions" style={{ marginTop: 8 }}>
          <button className="btn btn-sm btn-outline" onClick={onDismiss}>Dismiss</button>
        </div>
      )}
    </div>
  );
}

// ── Operations Alert ──────────────────────────────────────────────────────────

interface OpsAlertProps {
  card: OpsAlertData;
  variant?: 'compact' | 'detail';
  onDismiss?: () => void;
}

export function OperationsAlertCardComponent({ card, variant = 'detail', onDismiss }: OpsAlertProps) {
  const severityClass = card.severity === 'high' ? 'critical' : 'warning';
  const ageLabel = formatAge(card.created_at);
  const title = getOpsTitle(card);
  const body = getOpsBody(card);

  if (variant === 'compact') {
    return (
      <div className={`board-card-compact board-card--${severityClass}`}>
        <div className="board-card-name board-card-name--truncate">{title}</div>
        <span className={`board-card-pill pill--${severityClass}`}>{ageLabel}</span>
      </div>
    );
  }

  return (
    <div className={`action-card action-card--${severityClass}`}>
      <div className="action-card-header">
        <span className={`action-card-badge badge--${severityClass}`}>Operations</span>
        <span className="action-card-type-label">{ageLabel}</span>
      </div>
      <div className="action-card-title">{title}</div>
      <div className="action-card-meta" style={{ marginTop: 8 }}>{body}</div>
      {onDismiss && (
        <div className="po-card-actions" style={{ marginTop: 8 }}>
          <button className="btn btn-sm btn-outline" onClick={onDismiss}>Dismiss</button>
        </div>
      )}
    </div>
  );
}

function getOpsTitle(card: OpsAlertData): string {
  switch (card.alert_type) {
    case 'kitchen_slow':
      return `Kitchen slow — ${card.avg_prep_minutes} min avg prep`;
    case 'high_cancellations':
      return `High cancellations — ${Math.round((card.cancellation_rate ?? 0) * 100)}%`;
    case 'aov_drop':
      return `Low avg order value — ₹${card.current_aov_inr}`;
    case 'table_stale':
      return `${card.stale_count} table${(card.stale_count ?? 0) > 1 ? 's' : ''} may be forgotten`;
    case 'dead_period':
      return `No orders in ${card.dead_period_minutes} minutes`;
    default:
      return 'Operations alert';
  }
}

function getOpsBody(card: OpsAlertData): string {
  switch (card.alert_type) {
    case 'kitchen_slow':
      return `Prep time is ${card.multiplier}× baseline. Check kitchen capacity.`;
    case 'high_cancellations':
      return `${card.cancelled_orders} orders cancelled this period. Investigate cause.`;
    case 'aov_drop':
      return `${Math.round((1 - (card.ratio ?? 0)) * 100)}% below normal this hour.`;
    case 'table_stale':
      return `Tables ${(card.stale_tables ?? []).map((t) => t.table_number).join(', ')} occupied with no active order.`;
    case 'dead_period':
      return `Zero completed orders since ${card.hour}:00. Check if all systems are running.`;
    default:
      return '';
  }
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

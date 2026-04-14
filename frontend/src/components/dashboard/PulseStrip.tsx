/**
 * PulseStrip — Zone 1, pinned top.
 *
 * Displays today's key metrics vs last week with change indicators.
 * Shown at all times; refreshed by parent polling every 30s.
 */

import { PulseMetrics } from '../../services/ownerDashboard';

interface Props {
  data: PulseMetrics;
  lastUpdated: Date;
}

export default function PulseStrip({ data, lastUpdated }: Props) {
  const revenueChange = data.revenue_vs_last_week_pct;
  const changeColor =
    revenueChange === null ? 'var(--color-text-muted)' :
    revenueChange >= 0 ? '#10B981' : '#EF4444';
  const changePrefix = revenueChange !== null && revenueChange >= 0 ? '+' : '';

  const secondsAgo = Math.floor((Date.now() - lastUpdated.getTime()) / 1000);
  const freshLabel = secondsAgo < 60 ? 'just now' : `${Math.floor(secondsAgo / 60)}m ago`;

  return (
    <div className="pulse-strip">
      <div className="pulse-metrics">
        <PulseMetric
          value={`₹${Math.round(data.revenue_today_inr).toLocaleString('en-IN')}`}
          label="Revenue today"
          sub={
            revenueChange !== null
              ? <span style={{ color: changeColor }}>{changePrefix}{revenueChange}% vs last week</span>
              : undefined
          }
          accent="#10B981"
        />
        <PulseMetric
          value={String(data.covers_today)}
          label="Covers"
          accent="#3B82F6"
        />
        <PulseMetric
          value={`₹${Math.round(data.avg_ticket_inr).toLocaleString('en-IN')}`}
          label="Avg ticket"
          accent="#8B5CF6"
        />
        <PulseMetric
          value={data.food_cost_pct !== null ? `${data.food_cost_pct}%` : '—'}
          label="Food cost %"
          accent={
            data.food_cost_pct === null ? 'var(--color-text-muted)' :
            data.food_cost_pct > 35 ? '#EF4444' :
            data.food_cost_pct > 30 ? '#F59E0B' : '#10B981'
          }
        />
        <div className="pulse-attention">
          {data.attention_count === 0 ? (
            <span className="pulse-all-clear">All clear</span>
          ) : (
            <span className="pulse-needs-attention">
              {data.attention_count} item{data.attention_count !== 1 ? 's' : ''} need attention
            </span>
          )}
        </div>
      </div>
      <div className="pulse-freshness">Updated {freshLabel}</div>
    </div>
  );
}

function PulseMetric({
  value,
  label,
  sub,
  accent,
}: {
  value: string;
  label: string;
  sub?: React.ReactNode;
  accent: string;
}) {
  return (
    <div className="pulse-metric">
      <div className="pulse-metric-value" style={{ color: accent }}>{value}</div>
      <div className="pulse-metric-label">{label}</div>
      {sub && <div className="pulse-metric-sub">{sub}</div>}
    </div>
  );
}

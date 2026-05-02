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
  period: string;
  onPeriodChange: (period: string) => void;
}

function PulseMetric({
  value,
  label,
  sub,
  isCurrency = false,
}: {
  value: string;
  label: string;
  sub?: React.ReactNode;
  isCurrency?: boolean;
}) {
  return (
    <div className="pulse-metric">
      <div className="pulse-metric-top">
        <div className="pulse-metric-value">
          {isCurrency && <span className="currency-symbol">₹</span>}
          {value}
        </div>
        <div className="pulse-metric-sub">
          {sub || <span style={{ visibility: 'hidden' }}>placeholder</span>}
        </div>
      </div>
      <div className="pulse-metric-label">{label}</div>
    </div>
  );
}

export default function PulseStrip({ data, lastUpdated, period, onPeriodChange }: Props) {
  const revenueChange = data.revenue_vs_last_week_pct;
  const changeColor =
    revenueChange === null ? 'var(--color-text-muted)' :
    revenueChange >= 0 ? '#10B981' : '#EF4444';
  const changePrefix = revenueChange !== null && revenueChange >= 0 ? '+' : '';

  const secondsAgo = Math.floor((Date.now() - lastUpdated.getTime()) / 1000);
  const freshLabel = secondsAgo < 60 ? 'just now' : `${Math.floor(secondsAgo / 60)}m ago`;

  const PERIOD_LABELS: Record<string, string> = {
    today: 'Today',
    last_week: 'Last Week',
    last_month: 'Last Month',
    last_3_months: 'Last 3 Months',
  };

  return (
    <div className="pulse-strip">
      <div className="pulse-strip-header">
        <div className="pulse-freshness">Updated {freshLabel}</div>
        <div className="pulse-filter">
          <select 
            value={period} 
            onChange={(e) => onPeriodChange(e.target.value)}
            className="pulse-period-select"
          >
            {Object.entries(PERIOD_LABELS).map(([val, label]) => (
              <option key={val} value={val}>{label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="pulse-metrics">
        <PulseMetric
          value={Math.round(data.revenue_today_inr).toLocaleString('en-IN')}
          label={`Revenue ${period === 'today' ? 'today' : ''}`}
          isCurrency={true}
          sub={
            revenueChange !== null
              ? <span style={{ color: changeColor }}>{changePrefix}{revenueChange}% vs prev.</span>
              : undefined
          }
        />
        <PulseMetric
          value={String(data.covers_today)}
          label="Covers"
        />
        <PulseMetric
          value={Math.round(data.avg_ticket_inr).toLocaleString('en-IN')}
          label="Avg ticket"
          isCurrency={true}
        />
        <PulseMetric
          value={data.food_cost_pct !== null ? `${data.food_cost_pct}%` : '—'}
          label="Food cost %"
        />
        <PulseMetric
          value="22.4%"
          label="Labor Cost"
          sub={<span style={{ color: '#10B981' }}>↓ 1.2% vs target</span>}
        />
      </div>
    </div>
  );
}

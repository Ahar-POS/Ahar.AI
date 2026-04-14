/**
 * RevenuePatternPanel — Zone 3.
 *
 * Bar chart: today's hourly revenue vs 30-day historical average.
 * Hours with >30% deviation flagged as anomalies.
 * Pure CSS bar chart — no external chart library required.
 */

import { RevenuePatternData, HourSlot } from '../../services/ownerDashboard';

interface Props {
  data: RevenuePatternData;
  onRefresh: () => void;
  loading: boolean;
}

export default function RevenuePatternPanel({ data, onRefresh, loading }: Props) {
  // Only show business hours with any data to keep the chart readable
  const activeHours = data.hours.filter(
    (h) => h.today_revenue_inr > 0 || h.historical_avg_inr > 0
  );
  const displayHours = activeHours.length > 0 ? activeHours : data.hours.slice(6, 23);

  const maxVal = Math.max(
    ...displayHours.map((h) => Math.max(h.today_revenue_inr, h.historical_avg_inr)),
    1
  );

  return (
    <div className="z3-panel">
      <div className="z3-panel-header">
        <div className="z3-panel-title-row">
          <span className="z3-panel-title">Revenue Pattern</span>
          <span className="z3-panel-subtitle">Today vs 30-day avg</span>
        </div>
        <div className="z3-panel-controls">
          <div className="rev-legend">
            <span className="rev-legend-dot rev-legend-dot--today" />Today
            <span className="rev-legend-dot rev-legend-dot--avg" />Avg
          </div>
          <button className="z3-refresh-btn" onClick={onRefresh} disabled={loading}>
            {loading ? '…' : 'Refresh'}
          </button>
        </div>
      </div>

      {data.anomalous_hours.length > 0 && (
        <div className="rev-anomaly-note">
          Anomalous hours: {data.anomalous_hours.map((h) => `${h}:00`).join(', ')}
        </div>
      )}

      <div className="rev-chart">
        {displayHours.map((slot) => (
          <HourBar key={slot.hour} slot={slot} maxVal={maxVal} isCurrent={slot.hour === data.current_hour} />
        ))}
      </div>

      <div className="rev-total">
        Today total: <strong>₹{Math.round(data.today_total_inr).toLocaleString('en-IN')}</strong>
      </div>
    </div>
  );
}

function HourBar({
  slot,
  maxVal,
  isCurrent,
}: {
  slot: HourSlot;
  maxVal: number;
  isCurrent: boolean;
}) {
  const todayPct = (slot.today_revenue_inr / maxVal) * 100;
  const avgPct = (slot.historical_avg_inr / maxVal) * 100;
  const barClass = slot.anomaly
    ? `rev-bar-today rev-bar-today--${slot.anomaly}`
    : 'rev-bar-today';

  return (
    <div className={`rev-hour${isCurrent ? ' rev-hour--current' : ''}`} title={
      `${slot.label}: Today ₹${slot.today_revenue_inr.toFixed(0)} / Avg ₹${slot.historical_avg_inr.toFixed(0)}`
    }>
      <div className="rev-bars">
        <div className="rev-bar-avg" style={{ height: `${avgPct}%` }} />
        <div className={barClass} style={{ height: `${todayPct}%` }} />
      </div>
      <div className="rev-hour-label">{slot.hour}</div>
    </div>
  );
}

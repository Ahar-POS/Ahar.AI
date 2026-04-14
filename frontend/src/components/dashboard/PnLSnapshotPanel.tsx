/**
 * PnLSnapshotPanel — Zone 3.
 *
 * Month-to-date revenue, COGS, waste, gross margin %.
 * Shows a note when COGS data is unavailable.
 */

import { PnLSnapshotData } from '../../services/ownerDashboard';

interface Props {
  data: PnLSnapshotData;
  onRefresh: () => void;
  loading: boolean;
}

export default function PnLSnapshotPanel({ data, onRefresh, loading }: Props) {
  const grossMarginColor =
    data.gross_margin_pct === null ? 'var(--color-text-muted)' :
    data.gross_margin_pct < 40 ? '#EF4444' :
    data.gross_margin_pct < 55 ? '#F59E0B' : '#10B981';

  return (
    <div className="z3-panel">
      <div className="z3-panel-header">
        <div className="z3-panel-title-row">
          <span className="z3-panel-title">P&amp;L Snapshot</span>
          <span className="z3-panel-subtitle">{data.period.label}</span>
        </div>
        <button className="z3-refresh-btn" onClick={onRefresh} disabled={loading}>
          {loading ? '…' : 'Refresh'}
        </button>
      </div>

      <div className="pnl-grid">
        <PnLCard
          label="Revenue"
          value={`₹${Math.round(data.revenue_inr).toLocaleString('en-IN')}`}
          sub={`${data.order_count} orders`}
          accent="#10B981"
        />
        <PnLCard
          label="COGS"
          value={data.cogs_data_available
            ? `₹${Math.round(data.cogs_inr).toLocaleString('en-IN')}`
            : '—'}
          sub={data.cogs_data_available
            ? (data.food_cost_pct !== null ? `${data.food_cost_pct}% food cost` : undefined)
            : 'No movement data yet'}
          accent="#3B82F6"
        />
        <PnLCard
          label="Gross profit"
          value={data.gross_margin_pct !== null
            ? `₹${Math.round(data.gross_profit_inr).toLocaleString('en-IN')}`
            : '—'}
          sub={data.gross_margin_pct !== null ? undefined : undefined}
          accent={grossMarginColor}
          extra={data.gross_margin_pct !== null
            ? <span style={{ color: grossMarginColor, fontSize: 13, fontWeight: 600 }}>
                {data.gross_margin_pct}% margin
              </span>
            : undefined}
        />
        <PnLCard
          label="Waste"
          value={`₹${Math.round(data.waste_inr).toLocaleString('en-IN')}`}
          accent={data.waste_inr > 0 ? '#F59E0B' : 'var(--color-text-muted)'}
        />
      </div>

      {!data.cogs_data_available && (
        <div className="pnl-note">
          COGS will appear once stock movement data is recorded against sales.
        </div>
      )}
    </div>
  );
}

function PnLCard({
  label,
  value,
  sub,
  accent,
  extra,
}: {
  label: string;
  value: string;
  sub?: string;
  accent: string;
  extra?: React.ReactNode;
}) {
  return (
    <div className="pnl-card">
      <div className="pnl-card-label">{label}</div>
      <div className="pnl-card-value" style={{ color: accent }}>{value}</div>
      {sub && <div className="pnl-card-sub">{sub}</div>}
      {extra}
    </div>
  );
}

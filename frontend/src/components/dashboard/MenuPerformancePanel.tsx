/**
 * MenuPerformancePanel — Zone 3.
 *
 * Items ranked by contribution margin with revenue, volume, margin %.
 * Agent annotations shown inline on rows.
 */

import { useState } from 'react';
import { MenuPerformanceData } from '../../services/ownerDashboard';

interface Props {
  data: MenuPerformanceData;
  onRefresh: () => void;
  loading: boolean;
}

export default function MenuPerformancePanel({ data, onRefresh, loading }: Props) {
  const [sortBy, setSortBy] = useState<'profit' | 'revenue' | 'margin_percentage' | 'volume'>('profit');

  const sorted = [...data.items].sort((a, b) => b[sortBy] - a[sortBy]);

  return (
    <div className="z3-panel">
      <div className="z3-panel-header">
        <div className="z3-panel-title-row">
          <span className="z3-panel-title">Menu Performance</span>
          <span className="z3-panel-subtitle">Last {data.period_days} days</span>
        </div>
        <div className="z3-panel-controls">
          <select
            className="z3-sort-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          >
            <option value="profit">By profit</option>
            <option value="revenue">By revenue</option>
            <option value="margin_percentage">By margin %</option>
            <option value="volume">By volume</option>
          </select>
          <button className="z3-refresh-btn" onClick={onRefresh} disabled={loading}>
            {loading ? '…' : 'Refresh'}
          </button>
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className="z3-empty">No sales data for this period.</div>
      ) : (
        <div className="z3-table-wrap">
          <table className="z3-table">
            <thead>
              <tr>
                <th>Item</th>
                <th className="z3-num">Revenue</th>
                <th className="z3-num">Profit</th>
                <th className="z3-num">Margin</th>
                <th className="z3-num">Volume</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((item) => (
                <tr key={item.item_id} className={item.annotation ? 'z3-row--annotated' : ''}>
                  <td>
                    <div className="z3-item-name">{item.item_name}</div>
                    {item.annotation && (
                      <div className="z3-annotation">{item.annotation}</div>
                    )}
                  </td>
                  <td className="z3-num">₹{Math.round(item.revenue).toLocaleString('en-IN')}</td>
                  <td className="z3-num">₹{Math.round(item.profit).toLocaleString('en-IN')}</td>
                  <td className="z3-num">
                    <MarginBadge pct={item.margin_percentage} />
                  </td>
                  <td className="z3-num">{item.volume}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MarginBadge({ pct }: { pct: number }) {
  const color = pct < 0 ? '#EF4444' : pct < 25 ? '#F59E0B' : '#10B981';
  return <span style={{ color, fontWeight: 600 }}>{pct.toFixed(1)}%</span>;
}

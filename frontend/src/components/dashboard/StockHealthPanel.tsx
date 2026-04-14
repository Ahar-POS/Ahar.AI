/**
 * StockHealthPanel — Zone 3.
 *
 * Inventory items classified critical/low/good.
 * Sorted critical first. Agent annotations inline.
 */

import { StockHealthData } from '../../services/ownerDashboard';

interface Props {
  data: StockHealthData;
  onRefresh: () => void;
  loading: boolean;
}

export default function StockHealthPanel({ data, onRefresh, loading }: Props) {
  const { summary, items } = data;

  return (
    <div className="z3-panel">
      <div className="z3-panel-header">
        <div className="z3-panel-title-row">
          <span className="z3-panel-title">Stock Health</span>
        </div>
        <div className="z3-panel-controls">
          <div className="stock-summary-pills">
            {summary.critical > 0 && (
              <span className="stock-pill stock-pill--critical">{summary.critical} critical</span>
            )}
            {summary.low > 0 && (
              <span className="stock-pill stock-pill--low">{summary.low} low</span>
            )}
            <span className="stock-pill stock-pill--good">{summary.good} good</span>
          </div>
          <button className="z3-refresh-btn" onClick={onRefresh} disabled={loading}>
            {loading ? '…' : 'Refresh'}
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="z3-empty">No inventory data.</div>
      ) : (
        <div className="z3-table-wrap">
          <table className="z3-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>Category</th>
                <th className="z3-num">Stock</th>
                <th className="z3-num">Reorder at</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.material_id} className={item.annotation ? 'z3-row--annotated' : ''}>
                  <td>
                    <div className="z3-item-name">{item.material_name}</div>
                    {item.annotation && (
                      <div className="z3-annotation">{item.annotation}</div>
                    )}
                  </td>
                  <td className="z3-muted">{item.category ?? '—'}</td>
                  <td className="z3-num">{item.current_stock} {item.unit}</td>
                  <td className="z3-num z3-muted">{item.reorder_level} {item.unit}</td>
                  <td>
                    <span className={`stock-health-badge stock-health-badge--${item.health}`}>
                      {item.health}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

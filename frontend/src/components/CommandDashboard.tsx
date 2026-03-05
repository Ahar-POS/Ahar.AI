/**
 * CommandDashboard — metrics + alerts + recommendations overlay.
 * Fetches data from existing financial API endpoints.
 */

import { useEffect, useState } from 'react';
import { getFinancialMetrics, getFinancialAlerts, FinancialMetrics, FinancialAlert } from '../services/financial';
import './CommandDashboard.css';

interface CommandDashboardProps {
  onClose: () => void;
}

export default function CommandDashboard({ onClose }: CommandDashboardProps) {
  const [metrics, setMetrics] = useState<FinancialMetrics | null>(null);
  const [alerts, setAlerts] = useState<FinancialAlert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [m, a] = await Promise.all([
          getFinancialMetrics(90),  // 90 days to capture Oct-Jan data
          getFinancialAlerts('active', undefined, 4),
        ]);
        if (!cancelled) {
          setMetrics(m);
          setAlerts(a);
        }
      } catch {
        // Silently handle — dashboard shows placeholder
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="cmd-dash">
        <div className="cmd-dash-loader">
          <div className="spinner" />
        </div>
      </div>
    );
  }

  return (
    <div className="cmd-dash">
      <div className="cmd-dash-header">
        <h2 className="cmd-dash-title">Dashboard</h2>
        <button type="button" className="cmd-dash-close" onClick={onClose}>
          Back to Chat
        </button>
      </div>

      {/* Metrics */}
      <div className="cmd-dash-section-title">Key Metrics</div>
      <div className="cmd-dash-metrics">
        <MetricCard
          value={metrics && metrics.total_revenue !== undefined ? `₹${Math.round(metrics.total_revenue).toLocaleString()}` : '—'}
          label="Total Revenue (90d)"
          color="#10B981"
        />
        <MetricCard
          value={metrics && metrics.total_orders !== undefined ? String(metrics.total_orders) : '—'}
          label="Total Orders"
          color="#3B82F6"
        />
        <MetricCard
          value={metrics && metrics.avg_order_value !== undefined ? `₹${metrics.avg_order_value.toLocaleString()}` : '—'}
          label="Avg Order Value"
          color="#8B5CF6"
        />
        <MetricCard
          value={metrics && metrics.avg_daily_revenue !== undefined ? `₹${metrics.avg_daily_revenue.toLocaleString()}` : '—'}
          label="Avg Daily Revenue"
          color="#F59E0B"
        />
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <>
          <div className="cmd-dash-section-title">Active Alerts ({alerts.length})</div>
          <div className="cmd-dash-alerts">
            {alerts.slice(0, 4).map((alert) => (
              <div
                key={alert._id}
                className={`cmd-dash-alert cmd-dash-alert--${alert.severity ?? 'medium'}`}
              >
                <div className="cmd-dash-alert-type">{formatAlertType(alert.alert_type)}</div>
                <div className="cmd-dash-alert-text">{alert.reasoning}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Recommendations */}
      <div className="cmd-dash-section-title">Smart Recommendations</div>
      <div className="cmd-dash-recs">
        <RecCard title="Review high-cost items" desc="Optimize menu pricing to improve margins" color="#3B82F6" />
        <RecCard title="Monitor peak hours" desc="Staff accordingly for rush periods" color="#10B981" />
        <RecCard title="Track inventory waste" desc="Reduce spoilage with demand forecasting" color="#EF4444" />
      </div>
    </div>
  );
}

function MetricCard({ value, label, color }: { value: string; label: string; color: string }) {
  return (
    <div className="cmd-dash-metric">
      <div className="cmd-dash-metric-value" style={{ color }}>{value}</div>
      <div className="cmd-dash-metric-label">{label}</div>
    </div>
  );
}

function RecCard({ title, desc, color }: { title: string; desc: string; color: string }) {
  return (
    <div className="cmd-dash-rec" style={{ borderLeftColor: color }}>
      <div className="cmd-dash-rec-title">{title}</div>
      <div className="cmd-dash-rec-desc">{desc}</div>
    </div>
  );
}

function formatAlertType(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

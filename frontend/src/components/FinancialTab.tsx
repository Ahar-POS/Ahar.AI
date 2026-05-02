/**
 * Financial Tab Component for HomePage
 *
 * Displays financial alerts, metrics, and agent status
 */

import React, { useState, useEffect } from 'react';
import {
  getFinancialAlerts,
  getAlertsSummary,
  getFinancialMetrics,
  getAgentStatus,
  resolveAlert,
  triggerFinancialAgent,
  FinancialAlert,
  AlertsSummary,
  FinancialMetrics,
  AgentStatus
} from '../services/financial';
import './FinancialTab.css';

export const FinancialTab: React.FC = () => {
  const [alerts, setAlerts] = useState<FinancialAlert[]>([]);
  const [summary, setSummary] = useState<AlertsSummary | null>(null);
  const [metrics, setMetrics] = useState<FinancialMetrics | null>(null);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState(7);

  useEffect(() => {
    loadData();
  }, [selectedPeriod]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [alertsData, summaryData, metricsData, statusData] = await Promise.all([
        getFinancialAlerts('active'),
        getAlertsSummary(),
        getFinancialMetrics(selectedPeriod),
        getAgentStatus()
      ]);

      setAlerts(alertsData);
      setSummary(summaryData);
      setMetrics(metricsData);
      setAgentStatus(statusData);
    } catch (error) {
      console.error('Error loading financial data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerAgent = async () => {
    try {
      setTriggering(true);
      await triggerFinancialAgent();
      alert('Financial agent triggered successfully. Refreshing data in 5 seconds...');
      setTimeout(() => {
        loadData();
      }, 5000);
    } catch (error) {
      console.error('Error triggering agent:', error);
      alert('Failed to trigger financial agent');
    } finally {
      setTriggering(false);
    }
  };

  const handleResolveAlert = async (alertId: string) => {
    try {
      await resolveAlert(alertId);
      loadData();
    } catch (error) {
      console.error('Error resolving alert:', error);
      alert('Failed to resolve alert');
    }
  };

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'revenue_anomaly': return '📊';
      case 'high_cogs': return '💰';
      case 'low_margin_items': return '📉';
      case 'declining_revenue': return '⚠️';
      default: return '🔔';
    }
  };

  const getAlertColor = (severity?: string) => {
    switch (severity) {
      case 'high': return 'alert-high';
      case 'medium': return 'alert-medium';
      default: return 'alert-low';
    }
  };

  const formatCurrency = (amount: number | undefined | null) =>
    `₹${(amount ?? 0).toFixed(2)}`;
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  if (loading) {
    return <div className="financial-tab-loading">Loading financial data...</div>;
  }

  return (
    <div className="financial-tab">
      {/* Header with Agent Status and Trigger */}
      <div className="financial-header">
        <div className="agent-status-inline">
          <span className="status-label">Agent Status:</span>
          <span className={`status-badge status-${agentStatus?.status}`}>
            {agentStatus?.status || 'Unknown'}
          </span>
          <span className="status-schedule">
            {agentStatus?.scheduled_time || 'Not scheduled'}
          </span>
          {agentStatus?.last_run && (
            <span className="status-last-run">
              Last run: {formatDate(agentStatus.last_run.timestamp)}
            </span>
          )}
        </div>
        <button
          onClick={handleTriggerAgent}
          disabled={triggering}
          className="trigger-btn"
        >
          {triggering ? 'Running...' : '▶️ Run Agent'}
        </button>
      </div>

      {/* Metrics Grid */}
      <div className="metrics-section">
        <div className="metrics-header">
          <h3>📈 Financial Metrics</h3>
          <select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(Number(e.target.value))}
            className="period-select"
          >
            <option value={7}>Last 7 Days</option>
            <option value={30}>Last 30 Days</option>
            <option value={90}>Last 90 Days</option>
          </select>
        </div>

        {metrics && (
          <div className="metrics-grid">
            <div className="metric-box">
              <div className="metric-icon">💵</div>
              <div className="metric-info">
                <div className="metric-value">{formatCurrency(metrics.total_revenue)}</div>
                <div className="metric-label">Total Revenue</div>
              </div>
            </div>
            <div className="metric-box">
              <div className="metric-icon">🛒</div>
              <div className="metric-info">
                <div className="metric-value">{metrics.total_orders}</div>
                <div className="metric-label">Total Orders</div>
              </div>
            </div>
            <div className="metric-box">
              <div className="metric-icon">💳</div>
              <div className="metric-info">
                <div className="metric-value">{formatCurrency(metrics.avg_order_value)}</div>
                <div className="metric-label">Avg Order Value</div>
              </div>
            </div>
            <div className="metric-box">
              <div className="metric-icon">📅</div>
              <div className="metric-info">
                <div className="metric-value">{formatCurrency(metrics.avg_daily_revenue)}</div>
                <div className="metric-label">Avg Daily Revenue</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Alerts Summary */}
      {summary && summary.total_active_alerts > 0 && (
        <div className="alerts-summary-bar">
          <span className="summary-item">
            <strong>{summary.total_active_alerts}</strong> Active Alerts
          </span>
          {Object.entries(summary.by_severity).map(([severity, count]) => (
            <span key={severity} className={`summary-item severity-${severity}`}>
              <strong>{count}</strong> {severity}
            </span>
          ))}
        </div>
      )}

      {/* Alerts List */}
      <div className="alerts-section">
        <h3>🔔 Active Alerts ({alerts.length})</h3>

        {alerts.length === 0 ? (
          <div className="no-alerts-box">
            <div className="no-alerts-icon">✅</div>
            <div>
              <h4>All Clear!</h4>
              <p>No active financial alerts. Financial health looks good.</p>
            </div>
          </div>
        ) : (
          <div className="alerts-grid">
            {alerts.map((alert) => (
              <div key={alert._id} className={`alert-box ${getAlertColor(alert.severity)}`}>
                <div className="alert-box-header">
                  <div className="alert-title">
                    <span className="alert-icon">{getAlertIcon(alert.alert_type)}</span>
                    <span>{alert.alert_type.replace(/_/g, ' ').toUpperCase()}</span>
                  </div>
                  {alert.severity && (
                    <span className={`severity-badge ${alert.severity}`}>
                      {alert.severity}
                    </span>
                  )}
                </div>

                <div className="alert-box-body">
                  <p className="alert-reason">{alert.reasoning}</p>

                  {alert.details && (
                    <div className="alert-details-box">
                      {alert.details.date && <div><strong>Date:</strong> {alert.details.date}</div>}
                      {alert.details.cogs_percentage && (
                        <div><strong>COGS:</strong> {alert.details.cogs_percentage}%</div>
                      )}
                      {alert.details.trend_percentage && (
                        <div><strong>Trend:</strong> {alert.details.trend_percentage}%</div>
                      )}
                    </div>
                  )}
                </div>

                <div className="alert-box-footer">
                  <span className="alert-time">{formatDate(alert.created_at)}</span>
                  <button
                    onClick={() => handleResolveAlert(alert._id)}
                    className="resolve-btn"
                  >
                    ✓ Resolve
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

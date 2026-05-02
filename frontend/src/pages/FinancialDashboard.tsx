/**
 * Financial Dashboard Page
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
import './FinancialDashboard.css';

const FinancialDashboard: React.FC = () => {
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
      loadData(); // Refresh data
    } catch (error) {
      console.error('Error resolving alert:', error);
      alert('Failed to resolve alert');
    }
  };

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'revenue_anomaly':
        return '📊';
      case 'high_cogs':
        return '💰';
      case 'low_margin_items':
        return '📉';
      case 'declining_revenue':
        return '⚠️';
      default:
        return '🔔';
    }
  };

  const getAlertColor = (severity?: string) => {
    switch (severity) {
      case 'high':
        return 'alert-high';
      case 'medium':
        return 'alert-medium';
      default:
        return 'alert-low';
    }
  };

  const formatCurrency = (amount: number) => {
    return `₹${amount.toFixed(2)}`;
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  if (loading) {
    return (
      <div className="financial-dashboard loading">
        <div className="spinner">Loading financial data...</div>
      </div>
    );
  }

  return (
    <div className="financial-dashboard">
      <div className="dashboard-header">
        <h1>Financial Analytics Dashboard</h1>
        <div className="header-actions">
          <button
            onClick={handleTriggerAgent}
            disabled={triggering}
            className="trigger-button"
          >
            {triggering ? 'Running...' : '▶️ Run Agent Now'}
          </button>
        </div>
      </div>

      {/* Agent Status */}
      <div className="agent-status-card">
        <h3>🤖 Financial Agent Status</h3>
        <div className="status-info">
          <div className="status-item">
            <span className="label">Status:</span>
            <span className={`value status-${agentStatus?.status}`}>
              {agentStatus?.status || 'Unknown'}
            </span>
          </div>
          <div className="status-item">
            <span className="label">Scheduled:</span>
            <span className="value">{agentStatus?.scheduled_time || 'Not scheduled'}</span>
          </div>
          {agentStatus?.last_run && (
            <div className="status-item">
              <span className="label">Last Run:</span>
              <span className="value">
                {formatDate(agentStatus.last_run.timestamp)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Metrics Summary */}
      <div className="metrics-section">
        <div className="metrics-header">
          <h2>📈 Financial Metrics</h2>
          <select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(Number(e.target.value))}
            className="period-selector"
          >
            <option value={7}>Last 7 Days</option>
            <option value={30}>Last 30 Days</option>
            <option value={90}>Last 90 Days</option>
          </select>
        </div>

        {metrics && (
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-icon">💵</div>
              <div className="metric-content">
                <div className="metric-label">Total Revenue</div>
                <div className="metric-value">{formatCurrency(metrics.total_revenue)}</div>
                <div className="metric-subtitle">{selectedPeriod} days</div>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-icon">🛒</div>
              <div className="metric-content">
                <div className="metric-label">Total Orders</div>
                <div className="metric-value">{metrics.total_orders}</div>
                <div className="metric-subtitle">{selectedPeriod} days</div>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-icon">💳</div>
              <div className="metric-content">
                <div className="metric-label">Avg Order Value</div>
                <div className="metric-value">{formatCurrency(metrics.avg_order_value)}</div>
                <div className="metric-subtitle">per order</div>
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-icon">📅</div>
              <div className="metric-content">
                <div className="metric-label">Avg Daily Revenue</div>
                <div className="metric-value">{formatCurrency(metrics.avg_daily_revenue)}</div>
                <div className="metric-subtitle">per day</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Alerts Summary */}
      {summary && (
        <div className="alerts-summary">
          <h2>🔔 Alert Summary</h2>
          <div className="summary-stats">
            <div className="summary-stat">
              <div className="stat-value">{summary.total_active_alerts}</div>
              <div className="stat-label">Active Alerts</div>
            </div>
            <div className="summary-stat">
              <div className="stat-value">{summary.total_all_time}</div>
              <div className="stat-label">All Time</div>
            </div>
            {Object.entries(summary.by_severity).map(([severity, count]) => (
              <div key={severity} className="summary-stat">
                <div className={`stat-value severity-${severity}`}>{count}</div>
                <div className="stat-label">{severity} Priority</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Active Alerts */}
      <div className="alerts-section">
        <h2>⚠️ Active Alerts ({alerts.length})</h2>

        {alerts.length === 0 ? (
          <div className="no-alerts">
            <div className="no-alerts-icon">✅</div>
            <div className="no-alerts-text">
              <h3>All Clear!</h3>
              <p>No active financial alerts. Your restaurant's financial health looks good.</p>
            </div>
          </div>
        ) : (
          <div className="alerts-list">
            {alerts.map((alert) => (
              <div
                key={alert._id}
                className={`alert-card ${getAlertColor(alert.severity)}`}
              >
                <div className="alert-header">
                  <div className="alert-title">
                    <span className="alert-icon">{getAlertIcon(alert.alert_type)}</span>
                    <span className="alert-type">
                      {alert.alert_type.replace(/_/g, ' ').toUpperCase()}
                    </span>
                  </div>
                  {alert.severity && (
                    <span className={`alert-severity ${alert.severity}`}>
                      {alert.severity}
                    </span>
                  )}
                </div>

                <div className="alert-body">
                  <div className="alert-reasoning">{alert.reasoning}</div>

                  {alert.details && (
                    <div className="alert-details">
                      {alert.details.date && (
                        <div className="detail-item">
                          <strong>Date:</strong> {alert.details.date}
                        </div>
                      )}
                      {alert.details.cogs_percentage && (
                        <div className="detail-item">
                          <strong>COGS:</strong> {alert.details.cogs_percentage}%
                          (Target: {alert.details.target_range})
                        </div>
                      )}
                      {alert.details.trend_percentage && (
                        <div className="detail-item">
                          <strong>Trend:</strong> {alert.details.trend_percentage}%
                        </div>
                      )}
                      {alert.details.count && (
                        <div className="detail-item">
                          <strong>Affected Items:</strong> {alert.details.count}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="alert-footer">
                  <div className="alert-meta">
                    <span className="alert-date">{formatDate(alert.created_at)}</span>
                    <span className="alert-confidence">
                      Confidence: {(alert.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <button
                    onClick={() => handleResolveAlert(alert._id)}
                    className="resolve-button"
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

export default FinancialDashboard;

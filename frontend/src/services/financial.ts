/**
 * Financial analytics and alerts API service
 */

import api from './api';

export interface FinancialAlert {
  _id: string;
  alert_type: 'revenue_anomaly' | 'high_cogs' | 'low_margin_items' | 'declining_revenue';
  severity?: 'high' | 'medium' | 'low';
  status: 'active' | 'resolved';
  created_at: string;
  reasoning: string;
  confidence: number;
  details: any;
  date?: string;
}

export interface AlertsSummary {
  total_active_alerts: number;
  total_all_time: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
}

export interface FinancialMetrics {
  period_days: number;
  total_revenue: number;
  total_orders: number;
  avg_order_value: number;
  avg_daily_revenue: number;
}

export interface AgentStatus {
  status: string;
  last_run?: any;
  scheduled_time?: string;
}

/**
 * Get financial alerts with optional filters
 */
export const getFinancialAlerts = async (
  status: string = 'active',
  alertType?: string,
  limit: number = 50
): Promise<FinancialAlert[]> => {
  const params: any = { status, limit };
  if (alertType) params.alert_type = alertType;

  const response = await api.get('/financial/alerts', { params });
  return response.data.data;
};

/**
 * Get summary of alerts by type and severity
 */
export const getAlertsSummary = async (): Promise<AlertsSummary> => {
  const response = await api.get('/financial/alerts/summary');
  return response.data.data;
};

/**
 * Get financial metrics for specified period
 */
export const getFinancialMetrics = async (daysBack: number = 7): Promise<FinancialMetrics> => {
  const response = await api.get('/financial/metrics', {
    params: { days_back: daysBack }
  });
  return response.data.data;
};

/**
 * Resolve a financial alert
 */
export const resolveAlert = async (alertId: string): Promise<void> => {
  await api.post(`/financial/alerts/${alertId}/resolve`);
};

/**
 * Get financial agent status and last run info
 */
export const getAgentStatus = async (): Promise<AgentStatus> => {
  const response = await api.get('/financial/agent/status');
  return response.data.data;
};

/**
 * Manually trigger financial agent
 */
export const triggerFinancialAgent = async (): Promise<void> => {
  await api.post('/health/trigger-agent/financial');
};

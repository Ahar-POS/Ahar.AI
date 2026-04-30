/**
 * Agent trigger API functions.
 * Uses existing backend endpoints to trigger and monitor agents.
 */

import api from './api';

export interface AgentTriggerResponse {
  status: string;
  message: string;
}

export interface OrchestratorStatus {
  status: string;
  agents: Record<string, { last_run?: string; status: string }>;
}

/** Trigger a named agent via the health endpoint */
export async function triggerAgent(name: string): Promise<AgentTriggerResponse> {
  const response = await api.post(`/health/trigger-agent/${name}`);
  return response.data.data ?? response.data;
}

/** Get orchestrator status */
export async function getOrchestratorStatus(): Promise<OrchestratorStatus> {
  const response = await api.get('/health/orchestrator');
  return response.data.data ?? response.data;
}

/** Convenience wrappers */
export const triggerFinancialAgent = () => triggerAgent('financial');
export const triggerInventoryAgent = () => triggerAgent('inventory');
export const triggerDemandForecaster = () => triggerAgent('forecaster');

/** Outlet analysis via insights endpoint */
export async function triggerOutletAnalysis(): Promise<void> {
  const now = new Date();
  const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  await api.post('/insights/generate', {
    start_date: thirtyDaysAgo.toISOString().split('T')[0],
    end_date: now.toISOString().split('T')[0],
    scope: ['operational'],
  }, { timeout: 120000 });
}

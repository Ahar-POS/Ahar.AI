import apiClient from './api';

export interface InsightDetail {
  happening: string;
  why: string;
  actions: string[];
}

export type AgentSource = 'finance' | 'inventory' | 'customer';
export type Priority = 'high' | 'medium' | 'low';

export interface AgentInsight {
  id: string;
  agent: AgentSource;
  priority: Priority;
  category: string;
  headline: string;
  summary: string;
  impact_inr: number | null;
  detail: InsightDetail;
  created_at: string;
}

export async function getAgentFeed(): Promise<AgentInsight[]> {
  const res = await apiClient.get('/dashboard/agent-feed');
  return res.data.data.insights as AgentInsight[];
}

export async function dismissInsight(id: string): Promise<void> {
  await apiClient.post(`/dashboard/agent-feed/${id}/dismiss`);
}

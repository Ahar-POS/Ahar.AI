import axios from './api';

// ===== Request/Response Types =====

export interface StrategicInsightsRequest {
  start_date: string;
  end_date: string;
  compare_to_previous?: boolean;
}

export interface Evidence {
  metric: string;
  value: string;
  source_tool: string;
  sample_size: number;
  confidence_interval?: string;
  statistically_significant: boolean;
}

export interface Opportunity {
  id: string;
  category: 'revenue_growth' | 'cost_reduction' | 'operational_efficiency' | 'menu_optimization' | 'customer_experience';
  title: string;
  description: string;
  evidence: Evidence[];
  impact_min: number;
  impact_max: number;
  impact_expected: number;
  assumptions: string[];
  confidence: number;
  actionable_steps: string[];
  timeline: string;
  effort: 'low' | 'medium' | 'high';
}

export interface Risk {
  id: string;
  category: 'supply_chain' | 'financial' | 'operational' | 'compliance' | 'market';
  title: string;
  description: string;
  evidence: Evidence[];
  impact_min: number;
  impact_max: number;
  impact_expected: number;
  probability: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  mitigation_steps: string[];
  timeline: string;
}

export interface StrategicInsights {
  opportunities: Opportunity[];
  risks: Risk[];
  executive_summary: string;
  analysis_period: {
    start: string;
    end: string;
    duration_days: number;
  };
  iterations_used: number;
  generated_at: string;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  total_tokens: number;
  model: string;
  cost_usd: number;
}

export interface StrategicInsightsResponse {
  success: boolean;
  data: {
    insights: StrategicInsights;
    usage: TokenUsage;
    cache_hit: boolean;
    cache_key: string;
  };
  message: string;
}

export interface InsightFeedback {
  insight_id: string;
  insight_type: 'opportunity' | 'risk';
  helpful: boolean;
  action_taken?: boolean;
  actual_impact?: number;
  comments?: string;
}

// ===== Service API =====

export const strategicInsightsService = {
  /**
   * Generate strategic insights using AI agent analysis
   * @param request Strategic insights request with date range
   * @returns Promise with opportunities, risks, and usage data
   */
  async generateInsights(request: StrategicInsightsRequest): Promise<StrategicInsightsResponse> {
    const response = await axios.post('/insights/strategic', request, {
      timeout: 300000, // 5 minutes for agent analysis
    });
    return response.data;
  },

  /**
   * Submit feedback on an insight
   * @param insightId Opportunity or risk ID
   * @param feedback Feedback data
   * @returns Promise with success response
   */
  async submitFeedback(insightId: string, feedback: InsightFeedback): Promise<{ success: boolean; message: string }> {
    const response = await axios.post(`/insights/strategic/${insightId}/feedback`, feedback);
    return response.data;
  },

  /**
   * Clear cached strategic insights
   * @param cacheKey Cache key to clear, or 'all' to clear everything
   * @returns Promise with success response
   */
  async clearCache(cacheKey: string = 'all'): Promise<{ success: boolean; message: string }> {
    const response = await axios.delete(`/insights/strategic/cache/${cacheKey}`);
    return response.data;
  },
};

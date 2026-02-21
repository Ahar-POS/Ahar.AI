import axios from './api';

export interface InsightsRequest {
  start_date: string;
  end_date: string;
  scope: string[];
}

export interface Issue {
  id: string;
  category: string;
  title: string;
  root_cause: string;
  impact: string;
  recommendation: string;
  priority: string;
  estimated_savings: number;
}

export interface FinancialSummary {
  total_revenue: number;
  revenue_loss: number;
  avg_order_value: number;
  cancelled_orders_count: number;
  discount_amount: number;
}

export interface InventorySummary {
  total_stock_value: number;
  waste_value: number;
  low_stock_items: number;
  near_expiry_items: number;
}

export interface OperationalSummary {
  avg_kitchen_time_mins: number;
  table_turnover_rate: number;
  staff_efficiency_score: number;
  orders_completed: number;
  avg_fulfillment_time_mins?: number;
}

export interface InsightsResponse {
  critical_issues: Issue[];
  financial_summary: FinancialSummary;
  inventory_summary: InventorySummary;
  operational_summary: OperationalSummary;
  estimated_monthly_savings: number;
  analysis_period: {
    start: string;
    end: string;
  };
  generated_at: string;
  cache_key?: string;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
}

export interface InsightsGenerateResponse {
  success: boolean;
  data: {
    insights: InsightsResponse;
    cache_key?: string;
    usage?: TokenUsage;
  };
  message: string;
}

export interface CachedInsightsResponse {
  success: boolean;
  data: InsightsResponse;
  message: string;
}

export const insightsService = {
  /**
   * Generate AI insights for restaurant operations
   * @param request Insights request with date range and scope
   * @returns Promise with insights data and token usage
   */
  async generateInsights(request: InsightsRequest): Promise<InsightsGenerateResponse> {
    const response = await axios.post('/insights/generate', request, {
      timeout: 120000, // 2 minutes for AI analysis
    });
    return response.data;
  },

  /**
   * Get cached insights by cache key
   * @param cacheKey Cache key identifier
   * @returns Promise with cached insights
   */
  async getCachedInsights(cacheKey: string): Promise<CachedInsightsResponse> {
    const response = await axios.get(`/insights/cached/${cacheKey}`);
    return response.data;
  },
};

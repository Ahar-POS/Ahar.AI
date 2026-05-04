/**
 * Owner Dashboard API service
 *
 * Covers all 7 dashboard endpoints plus the PO review action.
 */

import api from './api';

// ── Types ──────────────────────────────────────────────────────────────────

export interface PulseMetrics {
  revenue_today_paise: number;
  revenue_today_inr: number;
  revenue_vs_last_week_pct: number | null;
  covers_today: number;
  avg_ticket_paise: number;
  avg_ticket_inr: number;
  food_cost_pct: number | null;
  attention_count: number;
  period?: string;
  is_average?: boolean;
}

export interface LowStockCard {
  card_type: 'low_stock';
  material_id: string;
  material_name: string;
  current_stock: number;
  reorder_level: number;
  unit: string;
  severity: 'critical' | 'low';
}

export interface POApprovalCard {
  card_type: 'po_approval';
  po_id: string;
  list_id: string;
  status: string;
  total_items: number;
  pending_items: number;
  total_cost_inr: number;
  generated_at: string;
  supplier_count: number;
}

export interface RevenueAnomalyCard {
  card_type: 'revenue_anomaly';
  alert_id: string;
  message?: string;
  hour?: number;
  ratio?: number;
  severity: 'high' | 'medium' | 'low';
  created_at: string;
}

export interface ChannelDipCard {
  card_type: 'channel_dip';
  alert_id: string;
  hour: number;
  channel_count: number;
  worst_ratio: number;
  channels: Array<{
    channel: string;
    current_revenue_inr: number;
    current_order_count: number;
    historical_avg_inr: number;
    ratio: number;
    zero_orders: boolean;
  }>;
  severity: 'high' | 'medium' | 'low';
  created_at: string;
}

export interface OperationsAlertCard {
  card_type: 'operations_alert';
  alert_type: 'kitchen_slow' | 'high_cancellations' | 'aov_drop' | 'table_stale' | 'dead_period';
  alert_id: string;
  severity: 'high' | 'medium' | 'low';
  created_at: string;
  // kitchen_slow
  avg_prep_minutes?: number;
  multiplier?: number;
  // high_cancellations
  cancellation_rate?: number;
  cancelled_orders?: number;
  // aov_drop
  current_aov_inr?: number;
  ratio?: number;
  // table_stale
  stale_count?: number;
  stale_tables?: Array<{ table_number: number }>;
  // dead_period
  dead_period_minutes?: number;
  hour?: number;
}

export interface ExpirySpecialCard {
  card_type: 'expiry_special';
  special_id: string;
  suggestion: string;
  material_name: string;
  expiry_date: string;
  created_at: string;
}

export interface PromotionSuggestionCard {
  card_type: 'promotion_suggestion';
  suggestion_id: string;
  promo_type: 'PERCENTAGE_OFF' | 'COMBO_DEAL' | 'EXPIRY_CLEAR' | 'SPIKE_LEVERAGE';
  menu_item_names: string[];
  discount_pct: number;
  description: string;
  reasoning: string;
  confidence: number;
  created_at: string;
}

export type ActionCard =
  | LowStockCard
  | POApprovalCard
  | RevenueAnomalyCard
  | ChannelDipCard
  | OperationsAlertCard
  | ExpirySpecialCard
  | PromotionSuggestionCard;

export interface ActionQueueData {
  total_cards: number;
  cards: ActionCard[];
}

export interface MenuPerformanceItem {
  item_id: string;
  item_name: string;
  revenue: number;
  profit: number;
  margin_percentage: number;
  volume: number;
  avg_order_value: number;
  cogs_per_serving: number;
  annotation?: string | null;
}

export interface MenuPerformanceData {
  period_days: number;
  items: MenuPerformanceItem[];
}

export interface StockItem {
  material_id: string;
  material_name: string;
  category: string;
  current_stock: number;
  reorder_level: number;
  unit: string;
  health: 'critical' | 'low' | 'good';
  annotation?: string | null;
}

export interface StockHealthData {
  summary: { critical: number; low: number; good: number };
  items: StockItem[];
}

export interface PnLSnapshotData {
  period: { start: string; end: string; label: string };
  revenue_inr: number;
  cogs_inr: number;
  waste_inr: number;
  gross_profit_inr: number;
  gross_margin_pct: number | null;
  food_cost_pct: number | null;
  order_count: number;
  cogs_data_available: boolean;
}

export interface HourSlot {
  hour: number;
  label: string;
  today_revenue_inr: number;
  historical_avg_inr: number;
  today_covers: number;
  anomaly: 'above_normal' | 'below_normal' | null;
}

export interface BrandHealthData {
  overall_rating: number;
  total_reviews: number;
  platforms: {
    swiggy: { rating: number; trend: 'up' | 'down' | 'stable'; label: string };
    zomato: { rating: number; trend: 'up' | 'down' | 'stable'; label: string };
    google: { rating: number; trend: 'up' | 'down' | 'stable'; label: string };
  };
  ai_synthesis: {
    highlights: string;
    improvements: string;
  };
  platform_distribution: Array<{ name: string; value: number; color: string }>;
}

export interface RevenuePatternData {
  hours: HourSlot[];
  current_hour: number;
  today_total_inr: number;
  anomalous_hours: number[];
}

export interface POItemDecision {
  material_id: string;
  action: 'approve' | 'reject';
  quantity?: number;
  reason?: string;
}

export interface POReviewResult {
  po_id: string;
  status: string;
  approved_items: number;
  rejected_items: number;
  pending_items: number;
  approved_total_paise: number;
}

// ── API calls ──────────────────────────────────────────────────────────────

export const getPulseMetrics = async (period: string = 'today'): Promise<PulseMetrics> => {
  const res = await api.get('/dashboard/pulse', { params: { period } });
  return res.data.data;
};

export const getActionQueue = async (): Promise<ActionQueueData> => {
  const res = await api.get('/dashboard/action-queue');
  return res.data.data;
};

export const dismissAlert = async (alertId: string): Promise<void> => {
  await api.patch(`/dashboard/alerts/${alertId}/dismiss`);
};

export const getMenuPerformance = async (periodDays = 7): Promise<MenuPerformanceData> => {
  const res = await api.get('/dashboard/menu-performance', {
    params: { period_days: periodDays },
  });
  return res.data.data;
};

export const getStockHealth = async (): Promise<StockHealthData> => {
  const res = await api.get('/dashboard/stock-health');
  return res.data.data;
};

export const getPnLSnapshot = async (): Promise<PnLSnapshotData> => {
  const res = await api.get('/dashboard/pnl-snapshot');
  return res.data.data;
};

export const getRevenuePattern = async (): Promise<RevenuePatternData> => {
  const res = await api.get('/dashboard/revenue-pattern');
  return res.data.data;
};

export const getBrandHealth = async (): Promise<BrandHealthData> => {
  const res = await api.get('/dashboard/brand-health');
  return res.data.data;
};

export const reviewPurchaseOrder = async (
  poId: string,
  items: POItemDecision[]
): Promise<POReviewResult> => {
  const res = await api.post(`/approvals/purchase-orders/${poId}/review`, { items });
  return res.data.data;
};

export const approveExpirySpecial = async (
  specialId: string,
  notes?: string
): Promise<void> => {
  await api.post(`/approvals/expiry-specials/${specialId}/approve`, { notes });
};

export const rejectExpirySpecial = async (
  specialId: string,
  notes?: string
): Promise<void> => {
  await api.post(`/approvals/expiry-specials/${specialId}/reject`, { notes });
};

export const approvePromotionSuggestion = async (
  suggestionId: string,
  notes?: string
): Promise<void> => {
  await api.post(`/approvals/promotion-suggestions/${suggestionId}/approve`, { notes });
};

export const rejectPromotionSuggestion = async (
  suggestionId: string,
  notes?: string
): Promise<void> => {
  await api.post(`/approvals/promotion-suggestions/${suggestionId}/reject`, { notes });
};

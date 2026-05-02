/**
 * Approval Dashboard Types
 *
 * TypeScript interfaces for shopping lists and approval workflow
 */

/**
 * Shopping list item urgency level
 */
export type ItemUrgency = "URGENT" | "STANDARD" | "LOW_PRIORITY";

/**
 * Shopping list status
 */
export type ShoppingListStatus = "pending" | "approved" | "rejected" | "partially_approved";

/**
 * Item approval status (for partial approvals)
 */
export type ItemStatus =
  | "pending"
  | "pending_review"
  | "auto_approved"
  | "owner_approved"
  | "owner_rejected"
  | "approved"
  | "rejected"
  | "ordered"
  | "delivered";

/**
 * Individual item in shopping list
 */
export interface ShoppingListItem {
  material_id: string;
  material_name: string;
  unit: string;
  current_stock: number;
  reorder_level: number;

  // Forecasting context
  daily_demand: number;
  days_until_stockout: number;

  // Reorder details
  quantity_to_order: number;
  unit_cost_inr: number;
  line_total_inr: number;

  // Urgency classification
  urgency: ItemUrgency;
  urgency_reason: string;

  // Supplier info
  supplier_id: string;
  supplier_name: string;
  lead_time_days: number;

  // Item status (for partial approvals)
  item_status?: ItemStatus;

  // LLM reasoning from the inventory agent
  agent_reason?: string;
  agent_decision?: "auto_approve" | "escalate" | "defer";
}

/**
 * Urgency summary for quick overview
 */
export interface UrgencySummary {
  urgent_count: number;
  standard_count: number;
  low_priority_count: number;
}

/**
 * Supplier breakdown for batch ordering
 */
export interface SupplierBreakdown {
  supplier_id: string;
  supplier_name: string;
  item_count: number;
  total_cost_inr: number;
  items: string[]; // material_ids
}

/**
 * Shopping list document
 */
export interface ShoppingList {
  _id: string;
  list_id: string;
  generated_at: string; // ISO date string
  generated_by: string;
  status: ShoppingListStatus;

  // Summary info
  urgency_summary: UrgencySummary;
  total_cost_inr: number;
  estimated_total: number;

  // Items
  items: ShoppingListItem[];
  supplier_breakdown: SupplierBreakdown[];

  // Agent context
  agent_decision_id: string;
  confidence_score: number;
  reasoning: string;

  // Approval tracking
  reviewed_at: string | null;
  reviewed_by: string | null;
  approval_notes: string | null;

  // Execution tracking (future use)
  executed_at: string | null;
  execution_status: string;
  execution_notes: string | null;
}

/**
 * Approval request body
 */
export interface ApprovalRequest {
  notes?: string;
}

/**
 * Partial approval request body
 */
export interface PartialApprovalRequest {
  material_ids: string[];
  notes?: string;
}

/**
 * Single per-item decision in a PO review
 */
export interface POItemDecision {
  material_id: string;
  action: "approve" | "reject";
  quantity?: number;
  reason?: string;
}

/**
 * Per-item PO review request
 */
export interface POReviewRequest {
  items: POItemDecision[];
}

/**
 * Approval statistics
 */
export interface ApprovalStats {
  pending: number;
  approved: number;
  rejected: number;
  partially_approved: number;
  total: number;
}

/**
 * API response for pending approvals
 */
export interface PendingApprovalsResponse {
  success: true;
  data: ShoppingList[];
  message: string;
  timestamp: string;
}

/**
 * API response for single shopping list
 */
export interface ShoppingListResponse {
  success: true;
  data: ShoppingList;
  message: string;
  timestamp: string;
}

/**
 * API response for approval action
 */
export interface ApprovalActionResponse {
  success: true;
  data: {
    approved?: boolean;
    rejected?: boolean;
    approved_items?: number;
    list_id: string;
  };
  message: string;
  timestamp: string;
}

/**
 * API response for approval history
 */
export interface ApprovalHistoryResponse {
  success: true;
  data: ShoppingList[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
  timestamp: string;
}

/**
 * API response for approval stats
 */
export interface ApprovalStatsResponse {
  success: true;
  data: ApprovalStats;
  message: string;
  timestamp: string;
}

/**
 * Filter options for approval history
 */
export interface ApprovalHistoryFilters {
  page?: number;
  limit?: number;
  status?: ShoppingListStatus;
}

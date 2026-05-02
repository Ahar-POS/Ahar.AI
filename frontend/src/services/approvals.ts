/**
 * Approvals API Service
 *
 * API client functions for shopping list approval workflow
 */

import api from './api';
import type {
  PendingApprovalsResponse,
  ShoppingListResponse,
  ApprovalActionResponse,
  ApprovalHistoryResponse,
  ApprovalStatsResponse,
  ApprovalRequest,
  PartialApprovalRequest,
  ApprovalHistoryFilters,
} from '../types/approvals';

const BASE_URL = '/approvals';

/**
 * Get all pending shopping lists requiring approval
 */
export const getPendingApprovals = async (): Promise<PendingApprovalsResponse> => {
  const response = await api.get<PendingApprovalsResponse>(`${BASE_URL}/pending`);
  return response.data;
};

/**
 * Get detailed shopping list by ID
 *
 * @param listId - MongoDB ObjectId of shopping list
 */
export const getShoppingListDetails = async (listId: string): Promise<ShoppingListResponse> => {
  const response = await api.get<ShoppingListResponse>(`${BASE_URL}/${listId}`);
  return response.data;
};

/**
 * Approve entire shopping list
 *
 * @param listId - MongoDB ObjectId of shopping list
 * @param request - Approval request with optional notes
 */
export const approveShoppingList = async (
  listId: string,
  request: ApprovalRequest = {}
): Promise<ApprovalActionResponse> => {
  const response = await api.post<ApprovalActionResponse>(
    `${BASE_URL}/${listId}/approve`,
    request
  );
  return response.data;
};

/**
 * Approve specific items in shopping list (partial approval)
 *
 * @param listId - MongoDB ObjectId of shopping list
 * @param request - Partial approval request with material IDs and optional notes
 */
export const approveShoppingListItems = async (
  list_id: string,
  request: PartialApprovalRequest
): Promise<ApprovalActionResponse> => {
  const response = await api.post<ApprovalActionResponse>(
    `${BASE_URL}/${list_id}/approve-items`,
    request
  );
  return response.data;
};

/**
 * Review specific items (approve/reject) in shopping list
 *
 * @param listId - MongoDB ObjectId of shopping list
 * @param request - Review request with item decisions
 */
export const reviewShoppingListItems = async (
  listId: string,
  request: POReviewRequest
): Promise<ApprovalActionResponse> => {
  const response = await api.post<ApprovalActionResponse>(
    `${BASE_URL}/purchase-orders/${listId}/review`,
    request
  );
  return response.data;
};

/**
 * Reject shopping list
 *
 * @param listId - MongoDB ObjectId of shopping list
 * @param request - Rejection request with optional notes
 */
export const rejectShoppingList = async (
  listId: string,
  request: ApprovalRequest = {}
): Promise<ApprovalActionResponse> => {
  const response = await api.post<ApprovalActionResponse>(
    `${BASE_URL}/${listId}/reject`,
    request
  );
  return response.data;
};

/**
 * Get approval history audit log
 *
 * @param filters - Optional filters for pagination and status
 */
export const getApprovalHistory = async (
  filters: ApprovalHistoryFilters = {}
): Promise<ApprovalHistoryResponse> => {
  const params = new URLSearchParams();

  if (filters.page) params.append('page', filters.page.toString());
  if (filters.limit) params.append('limit', filters.limit.toString());
  if (filters.status) params.append('status', filters.status);

  const response = await api.get<ApprovalHistoryResponse>(
    `${BASE_URL}/history?${params.toString()}`
  );
  return response.data;
};

/**
 * Get approval statistics
 */
export const getApprovalStats = async (): Promise<ApprovalStatsResponse> => {
  const response = await api.get<ApprovalStatsResponse>(`${BASE_URL}/stats`);
  return response.data;
};

/**
 * Get all Hyperpure purchase orders (read-only tracking)
 */
export const getHyperpureOrders = async (status?: string): Promise<{ data: HyperpureOrder[] }> => {
  const params = status ? `?status=${status}` : '';
  const response = await api.get<{ data: HyperpureOrder[] }>(`${BASE_URL}/hyperpure-orders${params}`);
  return response.data;
};

export interface HyperpureOrderItem {
  material_id: string;
  material_name: string;
  quantity: number;
  unit: string;
  unit_cost_inr: number;
  line_total_inr: number;
}

export interface HyperpureOrder {
  _id: string;
  po_number: string;
  source: string;
  status: 'pending' | 'fully_received';
  items: HyperpureOrderItem[];
  total_cost_inr: number;
  ordered_at: string;
  delivered_at?: string;
  created_at: string;
}

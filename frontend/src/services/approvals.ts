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

const BASE_URL = '/api/v1/approvals';

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
  listId: string,
  request: PartialApprovalRequest
): Promise<ApprovalActionResponse> => {
  const response = await api.post<ApprovalActionResponse>(
    `${BASE_URL}/${listId}/approve-items`,
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

/**
 * Tables API service.
 * 
 * Handles all table-related API calls.
 */

import apiClient, { getErrorMessage } from './api';
import {
  Table,
  TableStatus,
  CreateTableData,
  UpdateTableData,
  TableStats,
} from '../types/tables';

/**
 * API response structure for table endpoints.
 */
interface TableAPIResponse {
  success: boolean;
  data: Table | Table[];
  message: string;
  timestamp: string;
}

/**
 * Get all tables for the authenticated user's restaurant.
 * 
 * Restaurant ID is automatically determined from the authenticated user's session.
 * 
 * @param includeInactive - Whether to include inactive tables
 * @returns Promise resolving to array of tables
 * @throws Error if request fails
 */
export async function getTables(includeInactive = false): Promise<Table[]> {
  try {
    const response = await apiClient.get<TableAPIResponse>('/tables', {
      params: {
        include_inactive: includeInactive,
      },
    });
    
    return Array.isArray(response.data.data) ? response.data.data : [];
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Get tables filtered by status for the authenticated user's restaurant.
 * 
 * Restaurant ID is automatically determined from the authenticated user's session.
 * 
 * @param status - Table status to filter by
 * @returns Promise resolving to array of tables
 * @throws Error if request fails
 */
export async function getTablesByStatus(status: TableStatus): Promise<Table[]> {
  try {
    const response = await apiClient.get<TableAPIResponse>(`/tables/status/${status}`);
    
    return Array.isArray(response.data.data) ? response.data.data : [];
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Get a specific table by ID.
 * 
 * @param tableId - Table database ID
 * @returns Promise resolving to table data
 * @throws Error if table not found or request fails
 */
export async function getTable(tableId: string): Promise<Table> {
  try {
    const response = await apiClient.get<TableAPIResponse>(`/tables/${tableId}`);
    return response.data.data as Table;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Create a new table.
 * 
 * @param data - Table creation data
 * @returns Promise resolving to created table
 * @throws Error if creation fails
 */
export async function createTable(data: CreateTableData): Promise<Table> {
  try {
    const response = await apiClient.post<TableAPIResponse>('/tables', data);
    return response.data.data as Table;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Update table details.
 * 
 * @param tableId - Table database ID
 * @param data - Fields to update
 * @returns Promise resolving to updated table
 * @throws Error if update fails
 */
export async function updateTable(
  tableId: string,
  data: UpdateTableData
): Promise<Table> {
  try {
    const response = await apiClient.put<TableAPIResponse>(`/tables/${tableId}`, data);
    return response.data.data as Table;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Update table status.
 * 
 * @param tableId - Table database ID
 * @param status - New table status
 * @returns Promise resolving to updated table
 * @throws Error if update fails
 */
export async function updateTableStatus(
  tableId: string,
  status: TableStatus
): Promise<Table> {
  try {
    const response = await apiClient.patch<TableAPIResponse>(
      `/tables/${tableId}/status`,
      { status }
    );
    return response.data.data as Table;
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Delete a table (soft delete).
 * 
 * @param tableId - Table database ID
 * @returns Promise resolving when deletion is complete
 * @throws Error if deletion fails
 */
export async function deleteTable(tableId: string): Promise<void> {
  try {
    await apiClient.delete(`/tables/${tableId}`);
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Calculate table statistics.
 * 
 * @param tables - Array of tables
 * @returns Table statistics object
 */
export function calculateTableStats(tables: Table[]): TableStats {
  const stats: TableStats = {
    total: tables.length,
    available: 0,
    occupied: 0,
    reserved: 0,
    closed: 0,
  };
  
  tables.forEach((table) => {
    switch (table.status) {
      case TableStatus.AVAILABLE:
        stats.available++;
        break;
      case TableStatus.OCCUPIED:
        stats.occupied++;
        break;
      case TableStatus.RESERVED:
        stats.reserved++;
        break;
      case TableStatus.CLOSED:
        stats.closed++;
        break;
    }
  });
  
  return stats;
}

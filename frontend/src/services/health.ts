/**
 * Health check API service.
 * 
 * Provides functions to check API and database health status.
 */

import apiClient from './api';
import { APIResponse, HealthCheckData, DatabaseHealthData } from '../types/api';

/**
 * Check API health status.
 * 
 * @returns Promise with health check response
 */
export async function checkHealth(): Promise<APIResponse<HealthCheckData>> {
  const response = await apiClient.get<APIResponse<HealthCheckData>>('/health');
  return response.data;
}

/**
 * Check database health status.
 * 
 * @returns Promise with database health check response
 */
export async function checkDatabaseHealth(): Promise<APIResponse<DatabaseHealthData>> {
  const response = await apiClient.get<APIResponse<DatabaseHealthData>>('/health/db');
  return response.data;
}

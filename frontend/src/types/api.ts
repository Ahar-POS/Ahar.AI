/**
 * TypeScript interfaces for API communication.
 * 
 * These types match the backend API response format
 * as defined in the project rules.
 */

/**
 * Standard successful API response.
 */
export interface APIResponse<T = unknown> {
  success: true;
  data: T;
  message: string;
  timestamp: string;
}

/**
 * Error detail structure.
 */
export interface ErrorDetail {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

/**
 * Standard error API response.
 */
export interface APIErrorResponse {
  success: false;
  error: ErrorDetail;
  timestamp: string;
}

/**
 * Combined API response type.
 */
export type APIResult<T = unknown> = APIResponse<T> | APIErrorResponse;

/**
 * Pagination metadata.
 */
export interface PaginationInfo {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

/**
 * Paginated API response.
 */
export interface PaginatedResponse<T = unknown> {
  success: true;
  data: T[];
  pagination: PaginationInfo;
  timestamp: string;
}

/**
 * Health check response data.
 */
export interface HealthCheckData {
  status: 'healthy' | 'unhealthy';
  service: string;
  version: string;
}

/**
 * Database health check response data.
 */
export interface DatabaseHealthData {
  status: 'healthy' | 'unhealthy';
  database: 'connected' | 'disconnected';
}

/**
 * Type guard to check if response is an error.
 */
export function isAPIError(response: APIResult): response is APIErrorResponse {
  return response.success === false;
}

/**
 * Type guard to check if response is successful.
 */
export function isAPISuccess<T>(response: APIResult<T>): response is APIResponse<T> {
  return response.success === true;
}

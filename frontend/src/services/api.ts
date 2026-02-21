/**
 * API service configuration and base client.
 * 
 * Provides a configured Axios instance for making API calls
 * to the backend service.
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import { APIErrorResponse } from '../types/api';

/**
 * API configuration constants.
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_TIMEOUT = 180000; // 3 minutes (for Skills API P&L generation)

/**
 * Create configured Axios instance.
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Send cookies with requests for session authentication
});

/**
 * Request interceptor for adding auth headers, logging, etc.
 */
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token when authentication is implemented
    // const token = getAuthToken();
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor for error handling.
 */
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: AxiosError<APIErrorResponse>) => {
    // Handle specific error cases
    if (error.response) {
      // Server responded with error status
      const status = error.response.status;
      
      if (status === 401) {
        // Handle unauthorized - errors are handled by components via getErrorMessage
        // Redirect to login can be implemented here if needed
      } else if (status === 403) {
        // Handle forbidden - errors are handled by components
      } else if (status >= 500) {
        // Server errors are handled by components via getErrorMessage
      }
    } else if (error.request) {
      // Request made but no response received - handled by getErrorMessage
    } else {
      // Error setting up request - handled by getErrorMessage
    }
    
    return Promise.reject(error);
  }
);

export default apiClient;

/**
 * Helper to extract error message from API error response.
 */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<APIErrorResponse>;
    if (axiosError.response?.data?.error?.message) {
      return axiosError.response.data.error.message;
    }
    if (axiosError.message) {
      return axiosError.message;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
}

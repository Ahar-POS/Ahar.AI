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
const API_TIMEOUT = 30000; // 30 seconds

// #region agent log
fetch('http://127.0.0.1:7245/ingest/450c1218-4b04-4bd5-a655-01e95c07a305',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:14',message:'API_BASE_URL config',data:{API_BASE_URL,VITE_API_URL:import.meta.env.VITE_API_URL},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'D'})}).catch(()=>{});
// #endregion

/**
 * Create configured Axios instance.
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request interceptor for adding auth headers, logging, etc.
 */
apiClient.interceptors.request.use(
  (config) => {
    // #region agent log
    fetch('http://127.0.0.1:7245/ingest/450c1218-4b04-4bd5-a655-01e95c07a305',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:request-interceptor',message:'Outgoing request',data:{url:config.url,method:config.method,baseURL:config.baseURL,fullURL:`${config.baseURL}${config.url}`},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'B,D,E'})}).catch(()=>{});
    // #endregion
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
    // #region agent log
    fetch('http://127.0.0.1:7245/ingest/450c1218-4b04-4bd5-a655-01e95c07a305',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:response-success',message:'Response received',data:{status:response.status,url:response.config.url},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A,B'})}).catch(()=>{});
    // #endregion
    return response;
  },
  (error: AxiosError<APIErrorResponse>) => {
    // #region agent log
    fetch('http://127.0.0.1:7245/ingest/450c1218-4b04-4bd5-a655-01e95c07a305',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.ts:response-error',message:'Response error',data:{hasResponse:!!error.response,hasRequest:!!error.request,code:error.code,message:error.message,url:error.config?.url,status:error.response?.status},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'A,B,C'})}).catch(()=>{});
    // #endregion
    // Handle specific error cases
    if (error.response) {
      // Server responded with error status
      const status = error.response.status;
      
      if (status === 401) {
        // Handle unauthorized - redirect to login when auth is implemented
        console.error('Unauthorized access');
      } else if (status === 403) {
        console.error('Forbidden access');
      } else if (status >= 500) {
        console.error('Server error:', error.response.data);
      }
    } else if (error.request) {
      // Request made but no response received
      console.error('Network error - no response received');
    } else {
      // Error setting up request
      console.error('Request error:', error.message);
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

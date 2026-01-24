/**
 * Authentication API service.
 * 
 * Handles all authentication-related API calls.
 */

import apiClient, { getErrorMessage } from './api';
import {
  User,
  LoginRequest,
  RegisterRequest,
  AuthResponse,
} from '../types/auth';
import { APIResponse } from '../types/api';

/**
 * API response structure for auth endpoints.
 */
interface AuthAPIResponse {
  success: boolean;
  data: {
    user: User;
    session?: {
      expires_at: string;
    };
  };
  message: string;
  timestamp: string;
}

/**
 * Register a new user account.
 * 
 * @param data - Registration data (email, password, first_name, last_name)
 * @returns Promise resolving to AuthResponse with user data
 * @throws Error if registration fails
 */
export async function register(data: RegisterRequest): Promise<AuthResponse> {
  try {
    const response = await apiClient.post<AuthAPIResponse>('/auth/register', data);
    
    return {
      user: response.data.data.user,
      session: {
        token: '', // Token is in cookie, not returned in body
        expires_at: response.data.data.session?.expires_at || '',
        created_at: new Date().toISOString(),
      },
    };
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Login with email and password.
 * 
 * @param credentials - Login credentials
 * @returns Promise resolving to AuthResponse with user data
 * @throws Error if login fails
 */
export async function login(credentials: LoginRequest): Promise<AuthResponse> {
  try {
    const response = await apiClient.post<AuthAPIResponse>('/auth/login', credentials);
    
    return {
      user: response.data.data.user,
      session: {
        token: '', // Token is in cookie, not returned in body
        expires_at: response.data.data.session?.expires_at || '',
        created_at: new Date().toISOString(),
      },
    };
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Logout current session.
 * 
 * @returns Promise resolving when logout is complete
 */
export async function logout(): Promise<void> {
  try {
    await apiClient.post('/auth/logout');
  } catch (error) {
    // Even if logout fails on server, clear local state
    console.error('Logout error:', getErrorMessage(error));
  }
}

/**
 * Logout from all devices.
 * 
 * @returns Promise resolving when all sessions are invalidated
 * @throws Error if request fails
 */
export async function logoutAll(): Promise<void> {
  try {
    await apiClient.post('/auth/logout-all');
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

/**
 * Get current authenticated user.
 * 
 * @returns Promise resolving to User if authenticated, null otherwise
 */
export async function getCurrentUser(): Promise<User | null> {
  try {
    const response = await apiClient.get<AuthAPIResponse>('/auth/me');
    return response.data.data.user;
  } catch (error) {
    // User is not authenticated or session expired
    return null;
  }
}

/**
 * Check if user is currently authenticated.
 * 
 * @returns Promise resolving to boolean indicating auth status
 */
export async function checkAuth(): Promise<boolean> {
  const user = await getCurrentUser();
  return user !== null;
}

/**
 * TypeScript interfaces for authentication.
 * 
 * These types define the structure for user authentication,
 * sessions, and related API requests/responses.
 */

/**
 * User role enumeration.
 */
export type UserRole = 'admin';
// Future roles: 'waiter' | 'chef' | 'cashier'

/**
 * User account status.
 */
export type UserStatus = 'active' | 'inactive' | 'suspended';

/**
 * User data returned from API.
 */
export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  status: UserStatus;
  created_at: string;
  updated_at: string;
}

/**
 * Login request payload.
 */
export interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
}

/**
 * Registration request payload.
 */
export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
}

/**
 * Session data returned from API.
 */
export interface Session {
  token: string;
  expires_at: string;
  created_at: string;
}

/**
 * Authentication response from login/register.
 */
export interface AuthResponse {
  user: User;
  session: Session;
}

/**
 * Auth context state.
 */
export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

/**
 * Auth context actions.
 */
export interface AuthContextType extends AuthState {
  login: (credentials: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  checkSession: () => Promise<void>;
}

/**
 * Password validation result.
 */
export interface PasswordValidation {
  isValid: boolean;
  hasMinLength: boolean;
  hasLetter: boolean;
  hasNumber: boolean;
}

/**
 * Validate password strength.
 */
export function validatePassword(password: string): PasswordValidation {
  return {
    isValid: password.length >= 6 && /[a-zA-Z]/.test(password) && /\d/.test(password),
    hasMinLength: password.length >= 6,
    hasLetter: /[a-zA-Z]/.test(password),
    hasNumber: /\d/.test(password),
  };
}

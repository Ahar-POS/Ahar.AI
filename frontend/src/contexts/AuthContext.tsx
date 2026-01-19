/**
 * Authentication Context.
 * 
 * Provides authentication state and actions to the entire application.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';

import {
  User,
  LoginRequest,
  RegisterRequest,
  AuthContextType,
  AuthState,
} from '../types/auth';

import * as authService from '../services/auth';

/**
 * Default auth state.
 */
const defaultAuthState: AuthState = {
  user: null,
  isAuthenticated: false,
  isLoading: true,
};

/**
 * Auth context with default values.
 */
const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * Props for AuthProvider component.
 */
interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Authentication Provider Component.
 * 
 * Wraps the application and provides authentication state and actions.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>(defaultAuthState);

  /**
   * Check for existing session on mount.
   */
  const checkSession = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, isLoading: true }));
      const user = await authService.getCurrentUser();
      
      setState({
        user,
        isAuthenticated: user !== null,
        isLoading: false,
      });
    } catch (error) {
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  }, []);

  /**
   * Login with credentials.
   */
  const login = useCallback(async (credentials: LoginRequest) => {
    setState(prev => ({ ...prev, isLoading: true }));
    
    try {
      const response = await authService.login(credentials);
      
      setState({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error) {
      setState(prev => ({ ...prev, isLoading: false }));
      throw error;
    }
  }, []);

  /**
   * Register new user.
   */
  const register = useCallback(async (data: RegisterRequest) => {
    setState(prev => ({ ...prev, isLoading: true }));
    
    try {
      const response = await authService.register(data);
      
      setState({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error) {
      setState(prev => ({ ...prev, isLoading: false }));
      throw error;
    }
  }, []);

  /**
   * Logout current session.
   */
  const logout = useCallback(async () => {
    await authService.logout();
    
    setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
  }, []);

  /**
   * Logout from all devices.
   */
  const logoutAll = useCallback(async () => {
    await authService.logoutAll();
    
    setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
  }, []);

  /**
   * Check session on mount.
   */
  useEffect(() => {
    checkSession();
  }, [checkSession]);

  const value: AuthContextType = {
    ...state,
    login,
    register,
    logout,
    logoutAll,
    checkSession,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Hook to access auth context.
 * 
 * @returns AuthContextType with state and actions
 * @throws Error if used outside AuthProvider
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  
  return context;
}

export default AuthContext;

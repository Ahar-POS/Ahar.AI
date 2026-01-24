/**
 * Public route wrapper for unauthenticated-only pages.
 */

import React, { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface PublicRouteProps {
  children: ReactNode;
  redirectTo?: string;
}

/**
 * Render children only when unauthenticated.
 */
export default function PublicRoute({
  children,
  redirectTo = '/home',
}: PublicRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="page-centered">
        <span className="spinner" aria-label="Loading"></span>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to={redirectTo} replace />;
  }

  return <>{children}</>;
}

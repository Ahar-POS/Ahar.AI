"""
FastAPI dependencies for authentication and authorization.

Provides reusable dependencies for getting current user and restaurant context.
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.core.database import get_database
from app.models.user import UserResponse, UserRole
from app.services.auth_service import AuthService


def get_auth_service() -> AuthService:
    """Dependency to get auth service instance."""
    db = get_database()
    return AuthService(db)


def get_session_token(request: Request) -> Optional[str]:
    """
    Extract session token from cookie.
    
    Args:
        request: FastAPI request object.
        
    Returns:
        Session token or None if not found.
    """
    settings = get_settings()
    return request.cookies.get(settings.SESSION_COOKIE_NAME)


async def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """
    Get current authenticated user from session.
    
    This dependency extracts the session token from cookies,
    validates it, and returns the authenticated user.
    
    Args:
        request: FastAPI request object.
        auth_service: Auth service instance.
        
    Returns:
        UserResponse: Current authenticated user.
        
    Raises:
        HTTPException: If user is not authenticated or session is invalid.
    """
    session_token = get_session_token(request)
    
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": {
                    "code": "NOT_AUTHENTICATED",
                    "message": "You are not logged in",
                    "details": {}
                }
            }
        )
    
    user = await auth_service.get_current_user(session_token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_SESSION",
                    "message": "Your session has expired",
                    "details": {}
                }
            }
        )
    
    return user


async def get_admin_user(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """
    Ensure the current user has admin role.
    
    This dependency can be used by routes that should only be accessible
    to administrators, such as staff management endpoints or configuration
    screens.
    
    Args:
        current_user: Authenticated user obtained from get_current_user.
        
    Returns:
        UserResponse: The current authenticated admin user.
        
    Raises:
        HTTPException: If the user is not an admin.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You do not have permission to perform this action",
                    "details": {},
                },
            },
        )
    
    return current_user



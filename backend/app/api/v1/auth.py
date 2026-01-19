"""
Authentication API endpoints.

Handles user registration, login, logout, and session management.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.core.config import get_settings
from app.core.database import get_database
from app.models.user import UserCreate, UserLogin, UserResponse, UserRole
from app.models.session import SessionResponse
from app.services.auth_service import AuthService, AuthServiceError

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response Models
class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str
    remember_me: bool = False


class AuthResponse(BaseModel):
    """Authentication response with user and session data."""
    success: bool = True
    data: dict
    message: str
    timestamp: str


class MessageResponse(BaseModel):
    """Simple message response."""
    success: bool = True
    message: str
    timestamp: str


def get_auth_service() -> AuthService:
    """Dependency to get auth service instance."""
    db = get_database()
    return AuthService(db)


def get_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_user_agent(request: Request) -> Optional[str]:
    """Extract user agent from request."""
    return request.headers.get("User-Agent")


def get_session_token(request: Request) -> Optional[str]:
    """Extract session token from cookie."""
    settings = get_settings()
    return request.cookies.get(settings.SESSION_COOKIE_NAME)


def set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    """Set session cookie on response."""
    settings = get_settings()
    
    # Calculate max_age in seconds
    max_age = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Clear session cookie."""
    settings = get_settings()
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    response: Response,
    body: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Register a new user account.
    
    Creates a new user with Admin role and returns authentication data.
    """
    # #region agent log
    print(f"[DEBUG] Register endpoint hit - email: {body.email}, origin: {request.headers.get('origin')}", flush=True)
    # #endregion
    try:
        # Create user data with Admin role
        user_data = UserCreate(
            email=body.email,
            password=body.password,
            first_name=body.first_name,
            last_name=body.last_name,
            role=UserRole.ADMIN,
        )
        
        user, session = await auth_service.register(
            user_data,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        
        # Set session cookie
        set_session_cookie(response, session.token, session.expires_at)
        
        return AuthResponse(
            success=True,
            data={
                "user": user.model_dump(),
                "session": {
                    "expires_at": session.expires_at.isoformat(),
                }
            },
            message="Registration successful",
            timestamp=get_timestamp(),
        )
        
    except AuthServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {}
                },
                "timestamp": get_timestamp(),
            }
        )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Authenticate user and create session.
    
    Returns user data and sets session cookie.
    """
    # #region agent log
    print(f"[DEBUG] Login endpoint hit - email: {body.email}, origin: {request.headers.get('origin')}", flush=True)
    # #endregion
    try:
        credentials = UserLogin(
            email=body.email,
            password=body.password,
        )
        
        user, session = await auth_service.login(
            credentials,
            remember_me=body.remember_me,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        
        # Set session cookie
        set_session_cookie(response, session.token, session.expires_at)
        
        return AuthResponse(
            success=True,
            data={
                "user": user.model_dump(),
                "session": {
                    "expires_at": session.expires_at.isoformat(),
                }
            },
            message="Login successful",
            timestamp=get_timestamp(),
        )
        
    except AuthServiceError as e:
        status_code = status.HTTP_401_UNAUTHORIZED
        if e.code in ["ACCOUNT_SUSPENDED", "ACCOUNT_INACTIVE"]:
            status_code = status.HTTP_403_FORBIDDEN
            
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": {}
                },
                "timestamp": get_timestamp(),
            }
        )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Logout current session.
    
    Invalidates current session and clears cookie.
    """
    session_token = get_session_token(request)
    
    if session_token:
        await auth_service.logout(session_token)
    
    clear_session_cookie(response)
    
    return MessageResponse(
        success=True,
        message="Logged out successfully",
        timestamp=get_timestamp(),
    )


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Logout from all devices.
    
    Invalidates all sessions for the current user.
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
                },
                "timestamp": get_timestamp(),
            }
        )
    
    user = await auth_service.get_current_user(session_token)
    
    if not user:
        clear_session_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_SESSION",
                    "message": "Your session has expired",
                    "details": {}
                },
                "timestamp": get_timestamp(),
            }
        )
    
    count = await auth_service.logout_all(user.id)
    clear_session_cookie(response)
    
    return MessageResponse(
        success=True,
        message=f"Logged out from all {count} device(s)",
        timestamp=get_timestamp(),
    )


@router.get("/me", response_model=AuthResponse)
async def get_current_user(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Get current authenticated user.
    
    Returns user data if session is valid.
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
                },
                "timestamp": get_timestamp(),
            }
        )
    
    user = await auth_service.get_current_user(session_token)
    
    if not user:
        clear_session_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_SESSION",
                    "message": "Your session has expired",
                    "details": {}
                },
                "timestamp": get_timestamp(),
            }
        )
    
    return AuthResponse(
        success=True,
        data={"user": user.model_dump()},
        message="User retrieved successfully",
        timestamp=get_timestamp(),
    )

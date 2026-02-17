"""
Authentication service.

Handles business logic for user authentication, registration, and session management.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import (
    hash_password,
    verify_password,
    generate_session_token,
    get_session_expiry,
    validate_password_strength,
)
from app.models.user import (
    UserCreate,
    UserInDB,
    UserLogin,
    UserResponse,
    UserRole,
    UserStatus,
)
from app.models.session import SessionCreate, SessionInDB, SessionResponse
from app.repositories.user_repository import UserRepository
from app.repositories.session_repository import SessionRepository


class AuthServiceError(Exception):
    """Base exception for auth service errors."""
    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize auth service.
        
        Args:
            db: MongoDB database instance.
        """
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)

    async def register(
        self,
        user_data: UserCreate,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[UserResponse, SessionResponse]:
        """
        Register a new user and create initial session.
        
        Args:
            user_data: User registration data.
            ip_address: Client IP address.
            user_agent: Client user agent string.
            
        Returns:
            Tuple of (UserResponse, SessionResponse).
            
        Raises:
            AuthServiceError: If registration fails.
        """
        # Create user account
        user = await self._create_user(user_data)
        
        # Create session
        session = await self._create_session(
            user.id,
            remember_me=False,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        return self._to_user_response(user), self._to_session_response(session)

    async def create_user_without_session(self, user_data: UserCreate) -> UserResponse:
        """
        Create a new user account without creating a login session.
        
        This is used for admin-created users (e.g., staff accounts) where
        the admin should remain logged in and the new user should not be
        automatically authenticated.
        
        Args:
            user_data: User registration data.
            
        Returns:
            UserResponse: Created user data.
            
        Raises:
            AuthServiceError: If creation fails.
        """
        user = await self._create_user(user_data)
        return self._to_user_response(user)

    async def list_staff_for_restaurant(self, restaurant_id: str) -> List[UserResponse]:
        """
        List all staff users for a restaurant.

        Args:
            restaurant_id: Restaurant identifier (admin's restaurant).

        Returns:
            List of UserResponse for staff users, ordered by created_at.
        """
        users = await self.user_repo.list_by_restaurant_and_role(
            restaurant_id, UserRole.STAFF
        )
        return [self._to_user_response(u) for u in users]

    async def delete_staff_user(
        self, user_id: str, admin_restaurant_id: str
    ) -> None:
        """
        Permanently delete a staff user. Only staff users belonging to the
        same restaurant as the admin can be deleted. All their sessions are
        invalidated first.

        Args:
            user_id: ID of the staff user to delete.
            admin_restaurant_id: Restaurant ID of the requesting admin.

        Raises:
            AuthServiceError: If user not found, not staff, or wrong restaurant.
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AuthServiceError("User not found", "USER_NOT_FOUND")
        if user.role != UserRole.STAFF:
            raise AuthServiceError(
                "Only staff users can be removed from this list",
                "INVALID_ROLE",
            )
        if user.restaurant_id != admin_restaurant_id:
            raise AuthServiceError(
                "You can only remove staff from your own restaurant",
                "FORBIDDEN",
            )
        await self.session_repo.delete_user_sessions(user_id)
        deleted = await self.user_repo.delete(user_id)
        if not deleted:
            raise AuthServiceError("Failed to delete user", "DELETE_FAILED")

    async def _create_user(self, user_data: UserCreate) -> UserInDB:
        """
        Create a new user in the database.
        
        Shared logic between self-registration and admin-created users.
        
        Args:
            user_data: User registration data.
            
        Returns:
            UserInDB: Created user document.
            
        Raises:
            AuthServiceError: If creation fails.
        """
        # Validate password strength
        is_valid, error_msg = validate_password_strength(user_data.password)
        if not is_valid:
            raise AuthServiceError(error_msg, "WEAK_PASSWORD")
        
        # Check if email already exists
        if await self.user_repo.email_exists(user_data.email):
            raise AuthServiceError(
                "An account with this email already exists",
                "EMAIL_EXISTS"
            )
        
        # Generate restaurant_id if not provided (for new signups)
        # Each new user gets their own restaurant automatically
        if not user_data.restaurant_id:
            user_data.restaurant_id = str(uuid.uuid4())
        
        # Ensure restaurant_id is set (should always be after this point)
        if not user_data.restaurant_id:
            raise AuthServiceError(
                "Restaurant ID is required",
                "MISSING_RESTAURANT_ID"
            )
        
        # Hash password and create user
        password_hash = hash_password(user_data.password)
        return await self.user_repo.create(user_data, password_hash)

    async def login(
        self,
        credentials: UserLogin,
        remember_me: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[UserResponse, SessionResponse]:
        """
        Authenticate user and create session.
        
        Args:
            credentials: Login credentials (email, password).
            remember_me: Whether to extend session duration.
            ip_address: Client IP address.
            user_agent: Client user agent string.
            
        Returns:
            Tuple of (UserResponse, SessionResponse).
            
        Raises:
            AuthServiceError: If login fails.
        """
        # Find user by email
        user = await self.user_repo.get_by_email(credentials.email)
        
        if not user:
            raise AuthServiceError(
                "Invalid email or password",
                "INVALID_CREDENTIALS"
            )
        
        # Verify password
        if not verify_password(credentials.password, user.password_hash):
            raise AuthServiceError(
                "Invalid email or password",
                "INVALID_CREDENTIALS"
            )
        
        # Check user status
        if user.status != UserStatus.ACTIVE:
            if user.status == UserStatus.SUSPENDED:
                raise AuthServiceError(
                    "Your account has been suspended. Please contact support.",
                    "ACCOUNT_SUSPENDED"
                )
            else:
                raise AuthServiceError(
                    "Your account is inactive. Please contact support.",
                    "ACCOUNT_INACTIVE"
                )
        
        # Create session
        session = await self._create_session(
            user.id,
            remember_me=remember_me,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        return self._to_user_response(user), self._to_session_response(session)

    async def logout(self, session_token: str) -> bool:
        """
        Logout user by invalidating session.
        
        Args:
            session_token: Session token to invalidate.
            
        Returns:
            bool: True if session was invalidated.
        """
        return await self.session_repo.delete_by_token(session_token)

    async def logout_all(self, user_id: str, current_token: Optional[str] = None) -> int:
        """
        Logout user from all devices.
        
        Args:
            user_id: User's database ID.
            current_token: Optional token to keep (current session).
            
        Returns:
            int: Number of sessions invalidated.
        """
        if current_token:
            return await self.session_repo.delete_other_sessions(user_id, current_token)
        return await self.session_repo.delete_user_sessions(user_id)

    async def get_current_user(self, session_token: str) -> Optional[UserResponse]:
        """
        Get current user from session token.
        
        Args:
            session_token: Session token.
            
        Returns:
            UserResponse or None if session invalid.
        """
        session = await self.session_repo.get_valid_session(session_token)
        
        if not session:
            return None
        
        user = await self.user_repo.get_by_id(session.user_id)
        
        if not user or user.status != UserStatus.ACTIVE:
            return None
        
        return self._to_user_response(user)

    async def validate_session(self, session_token: str) -> bool:
        """
        Check if session is valid.
        
        Args:
            session_token: Session token to validate.
            
        Returns:
            bool: True if session is valid.
        """
        session = await self.session_repo.get_valid_session(session_token)
        return session is not None

    async def _create_session(
        self,
        user_id: str,
        remember_me: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> SessionInDB:
        """
        Create a new session for user.
        
        Args:
            user_id: User's database ID.
            remember_me: Whether to extend session duration.
            ip_address: Client IP address.
            user_agent: Client user agent string.
            
        Returns:
            SessionInDB: Created session.
        """
        session_data = SessionCreate(
            user_id=user_id,
            token=generate_session_token(),
            expires_at=get_session_expiry(remember_me),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        return await self.session_repo.create(session_data)

    def _to_user_response(self, user: UserInDB) -> UserResponse:
        """Convert UserInDB to UserResponse."""
        return UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            status=user.status,
            restaurant_id=user.restaurant_id,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def _to_session_response(self, session: SessionInDB) -> SessionResponse:
        """Convert SessionInDB to SessionResponse."""
        return SessionResponse(
            token=session.token,
            expires_at=session.expires_at,
            created_at=session.created_at,
        )

    async def ensure_indexes(self) -> None:
        """Create database indexes for auth collections."""
        await self.user_repo.ensure_indexes()
        await self.session_repo.ensure_indexes()

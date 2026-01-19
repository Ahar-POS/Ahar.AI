"""
Security utilities for authentication.

Provides password hashing and session token generation.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Tuple

from passlib.context import CryptContext

from app.core.config import get_settings

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plain text password.
    
    Args:
        password: Plain text password to hash.
        
    Returns:
        str: Hashed password string.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hash.
    
    Args:
        plain_password: Plain text password to verify.
        hashed_password: Hashed password to compare against.
        
    Returns:
        bool: True if password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def generate_session_token() -> str:
    """
    Generate a secure random session token.
    
    Returns:
        str: URL-safe random token (64 characters).
    """
    return secrets.token_urlsafe(48)


def get_session_expiry(remember_me: bool = False) -> datetime:
    """
    Calculate session expiry timestamp.
    
    Args:
        remember_me: If True, use extended session duration.
        
    Returns:
        datetime: UTC timestamp when session expires.
    """
    settings = get_settings()
    
    if remember_me:
        duration = timedelta(days=settings.SESSION_REMEMBER_ME_DAYS)
    else:
        duration = timedelta(hours=settings.SESSION_EXPIRE_HOURS)
    
    return datetime.now(timezone.utc) + duration


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password meets minimum requirements.
    
    Requirements:
    - Minimum 6 characters
    - At least one letter
    - At least one number
    
    Args:
        password: Password to validate.
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    
    has_letter = any(c.isalpha() for c in password)
    has_number = any(c.isdigit() for c in password)
    
    if not has_letter:
        return False, "Password must contain at least one letter"
    
    if not has_number:
        return False, "Password must contain at least one number"
    
    return True, ""

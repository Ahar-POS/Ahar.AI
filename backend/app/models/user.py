"""
User model definitions.

Defines the User schema and related enums for the authentication system.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    # Future roles (commented for now, Admin only initially)
    # WAITER = "waiter"
    # CHEF = "chef"
    # CASHIER = "cashier"


class UserStatus(str, Enum):
    """User account status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class UserBase(BaseModel):
    """Base user fields shared across models."""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    role: UserRole = UserRole.ADMIN
    status: UserStatus = UserStatus.ACTIVE
    restaurant_id: Optional[str] = Field(None, min_length=1, description="Restaurant identifier for multi-tenancy")


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    """Schema for user login request."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Schema for updating user details."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    status: Optional[UserStatus] = None
    # Note: restaurant_id is intentionally not updatable for security


class UserInDB(UserBase):
    """User model as stored in database."""
    id: str = Field(..., alias="_id")
    password_hash: str
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class UserResponse(BaseModel):
    """User data returned to clients (no sensitive fields)."""
    id: str
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    status: UserStatus
    restaurant_id: Optional[str]  # Optional for backward compatibility during migration
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

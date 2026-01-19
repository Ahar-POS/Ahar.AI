"""
Session model definitions.

Defines the Session schema for server-side session management.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SessionBase(BaseModel):
    """Base session fields."""
    user_id: str
    token: str
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class SessionCreate(SessionBase):
    """Schema for creating a new session."""
    pass


class SessionInDB(SessionBase):
    """Session model as stored in database."""
    id: str = Field(..., alias="_id")
    created_at: datetime

    class Config:
        populate_by_name = True


class SessionResponse(BaseModel):
    """Session data returned to clients."""
    token: str
    expires_at: datetime
    created_at: datetime

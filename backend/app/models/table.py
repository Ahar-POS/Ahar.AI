"""
Table model definitions.

Defines the Table schema for restaurant table management.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TableStatus(str, Enum):
    """Table status enumeration."""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    CLOSED = "closed"  # For maintenance or unavailable tables


class TableBase(BaseModel):
    """Base table fields shared across models."""
    table_number: int = Field(..., ge=1, description="Table number (must be positive)")
    location: str = Field(..., min_length=1, max_length=100, description="Table location/name (e.g., 'Window Seat', 'Patio A')")
    capacity: int = Field(..., ge=1, le=20, description="Seating capacity")
    status: TableStatus = TableStatus.AVAILABLE


class TableCreate(TableBase):
    """Schema for creating a new table."""
    created_by_user_id: Optional[str] = Field(None, description="User who created this table (auto-set from authenticated user)")


class TableUpdate(BaseModel):
    """Schema for updating table details."""
    location: Optional[str] = Field(None, min_length=1, max_length=100)
    capacity: Optional[int] = Field(None, ge=1, le=20)
    status: Optional[TableStatus] = None
    is_active: Optional[bool] = None


class TableInDB(TableBase):
    """Table model as stored in database."""
    id: str = Field(..., alias="_id")
    is_active: bool = True
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True


class TableResponse(BaseModel):
    """Table data returned to clients."""
    id: str
    table_number: int
    location: str
    capacity: int
    status: TableStatus
    is_active: bool
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

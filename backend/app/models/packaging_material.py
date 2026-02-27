"""
Packaging Material model for inventory and cost tracking.

Stores packaging materials like boxes, bags, stickers, cutlery, etc.
Used for calculating packaging costs in P&L.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PackagingCategory(str, Enum):
    """Packaging material categories."""
    PRIMARY = "PRIMARY"  # Main packaging - boxes, containers
    SECONDARY = "SECONDARY"  # Additional packaging - bags, tissue, cutlery
    LABELS = "LABELS"  # Stickers, labels, tamper seals


class PackagingMaterialBase(BaseModel):
    """Base packaging material fields."""
    packaging_id: str = Field(..., description="Unique packaging material identifier")
    packaging_name: str = Field(..., description="Name of the packaging material")
    category: PackagingCategory = Field(..., description="Packaging category")
    unit_cost_inr: int = Field(..., ge=0, description="Cost per unit in paise")
    unit: str = Field(..., description="Unit of measurement (Piece, Gram, etc.)")
    supplier_id: str = Field(..., description="Supplier identifier")
    description: Optional[str] = Field(None, description="Additional details about the material")


class PackagingMaterialCreate(PackagingMaterialBase):
    """Schema for creating a new packaging material."""
    pass


class PackagingMaterialUpdate(BaseModel):
    """Schema for updating packaging material details."""
    packaging_name: Optional[str] = None
    category: Optional[PackagingCategory] = None
    unit_cost_inr: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = None
    supplier_id: Optional[str] = None
    description: Optional[str] = None


class PackagingMaterialInDB(PackagingMaterialBase):
    """Packaging material as stored in database."""
    id: str = Field(..., alias="_id")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class PackagingMaterialResponse(BaseModel):
    """Packaging material data returned to clients."""
    id: str
    packaging_id: str
    packaging_name: str
    category: PackagingCategory
    unit_cost_inr: int
    unit: str
    supplier_id: str
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

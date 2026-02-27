"""
Packaging BOM (Bill of Materials) model.

Links menu items to their packaging requirements.
Specifies which packaging materials are needed per menu item.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PackagingBOMBase(BaseModel):
    """Base packaging BOM fields."""
    menu_item_id: str = Field(..., description="Menu item identifier")
    packaging_material_id: str = Field(..., description="Packaging material identifier")
    quantity_per_serving: float = Field(..., gt=0, description="Quantity needed per menu item serving")
    is_critical: bool = Field(True, description="Whether this packaging is essential")


class PackagingBOMCreate(PackagingBOMBase):
    """Schema for creating a new packaging BOM entry."""
    pass


class PackagingBOMUpdate(BaseModel):
    """Schema for updating packaging BOM details."""
    quantity_per_serving: Optional[float] = Field(None, gt=0)
    is_critical: Optional[bool] = None


class PackagingBOMInDB(PackagingBOMBase):
    """Packaging BOM as stored in database."""
    id: str = Field(..., alias="_id")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class PackagingBOMResponse(BaseModel):
    """Packaging BOM data returned to clients."""
    id: str
    menu_item_id: str
    packaging_material_id: str
    quantity_per_serving: float
    is_critical: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

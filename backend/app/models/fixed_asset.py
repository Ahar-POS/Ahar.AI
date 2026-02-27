"""
Fixed Asset model for depreciation and amortization tracking.

Stores equipment, furniture, and intangible assets with their
depreciation schedules for P&L calculation.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AssetCategory(str, Enum):
    """Fixed asset categories."""
    EQUIPMENT = "EQUIPMENT"  # Kitchen equipment (grills, fryers, etc.)
    FURNITURE = "FURNITURE"  # Furniture and fixtures
    BRAND = "BRAND"  # Brand setup, logo, marketing materials
    LEASEHOLD = "LEASEHOLD"  # Leasehold improvements


class FixedAssetBase(BaseModel):
    """Base fixed asset fields."""
    asset_id: str = Field(..., description="Unique asset identifier")
    asset_name: str = Field(..., description="Name of the asset")
    category: AssetCategory = Field(..., description="Asset category")
    purchase_cost_inr: int = Field(..., ge=0, description="Purchase cost in paise")
    useful_life_months: int = Field(..., gt=0, description="Useful life in months")
    purchase_date: datetime = Field(..., description="Date of purchase")
    description: Optional[str] = Field(None, description="Additional details about the asset")

    @property
    def monthly_depreciation_inr(self) -> int:
        """Calculate monthly depreciation in paise."""
        return self.purchase_cost_inr // self.useful_life_months


class FixedAssetCreate(FixedAssetBase):
    """Schema for creating a new fixed asset."""
    pass


class FixedAssetUpdate(BaseModel):
    """Schema for updating fixed asset details."""
    asset_name: Optional[str] = None
    category: Optional[AssetCategory] = None
    purchase_cost_inr: Optional[int] = Field(None, ge=0)
    useful_life_months: Optional[int] = Field(None, gt=0)
    purchase_date: Optional[datetime] = None
    description: Optional[str] = None


class FixedAssetInDB(FixedAssetBase):
    """Fixed asset as stored in database."""
    id: str = Field(..., alias="_id")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class FixedAssetResponse(BaseModel):
    """Fixed asset data returned to clients."""
    id: str
    asset_id: str
    asset_name: str
    category: AssetCategory
    purchase_cost_inr: int
    useful_life_months: int
    monthly_depreciation_inr: int
    purchase_date: datetime
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

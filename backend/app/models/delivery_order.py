"""
Delivery Order model definitions for P&L reporting.

Stores order data from external delivery platforms (Zomato, Swiggy) and walk-in orders.
Used for financial reporting and P&L analysis.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OrderChannel(str, Enum):
    """Order channel enumeration."""
    ZOMATO = "Zomato"
    SWIGGY = "Swiggy"
    WALK_IN = "WalkIn"


class DeliveryOrderBase(BaseModel):
    """Base delivery order fields."""
    order_date: datetime = Field(..., description="Order placement date")
    total_inr: float = Field(..., ge=0, description="Gross order value in INR")
    promo_discount_inr: float = Field(0, ge=0, description="Promotional discounts applied")
    item_discount_inr: float = Field(0, ge=0, description="Item-level discounts")
    tax_gst_inr: float = Field(0, ge=0, description="GST tax amount")
    delivery_fee_inr: float = Field(0, ge=0, description="Delivery charges")
    packaging_charge_inr: float = Field(0, ge=0, description="Packaging costs")
    order_channel: OrderChannel = Field(..., description="Sales channel")
    restaurant_id: str = Field(..., description="Restaurant identifier")


class DeliveryOrderCreate(DeliveryOrderBase):
    """Schema for creating a new delivery order record."""
    pass


class DeliveryOrderInDB(DeliveryOrderBase):
    """Delivery order model as stored in database."""
    id: str = Field(..., alias="_id")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class DeliveryOrderResponse(BaseModel):
    """Delivery order data returned to clients."""
    id: str
    order_date: datetime
    total_inr: float
    promo_discount_inr: float
    item_discount_inr: float
    tax_gst_inr: float
    delivery_fee_inr: float
    packaging_charge_inr: float
    order_channel: OrderChannel
    restaurant_id: str
    created_at: datetime

    class Config:
        from_attributes = True

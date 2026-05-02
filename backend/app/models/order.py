"""
Order model definitions.

Defines the Order schema for restaurant order management and kitchen operations.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class OrderType(str, Enum):
    """Order type enumeration."""
    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"


class OrderStatus(str, Enum):
    """
    Order-level status enumeration.
    
    Lifecycle:
    DRAFT → SENT_TO_KITCHEN → IN_PROGRESS → COMPLETED
              ↓
          CANCELLED (any time before COMPLETED)
    """
    DRAFT = "draft"  # Editable, not visible to kitchen
    SENT_TO_KITCHEN = "sent_to_kitchen"  # Immutable, waiting for kitchen to start
    IN_PROGRESS = "in_progress"  # Kitchen has started cooking
    COMPLETED = "completed"  # All items ready, order finished
    CANCELLED = "cancelled"  # Order cancelled (audit trail maintained)


class OrderItemStatus(str, Enum):
    """
    Item-level status within an order.
    
    Enables partial order completion and kitchen workflow.
    """
    PENDING = "pending"  # Not started
    COOKING = "cooking"  # Being prepared
    READY = "ready"  # Completed and ready to serve


class OrderItem(BaseModel):
    """
    Individual item within an order.

    Snapshots menu item details to preserve order history even if menu changes.
    """
    menu_item_id: str = Field(..., description="Reference to menu item")
    name_snapshot: str = Field(..., min_length=1, max_length=100, description="Menu item name at order time")
    price_snapshot: int = Field(..., ge=0, description="Item price in cents at order time")
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    notes: Optional[str] = Field(None, max_length=500, description="Special instructions (e.g., 'no garlic', 'extra spicy')")
    status: OrderItemStatus = OrderItemStatus.PENDING
    original_price_snapshot: Optional[int] = Field(None, description="Pre-discount price in paise")
    discount_paise: Optional[int] = Field(None, description="Discount applied in paise")
    applied_promo_id: Optional[str] = Field(None, description="promotions._id that was applied")


class OrderBase(BaseModel):
    """Base order fields shared across models."""
    restaurant_id: str = Field(..., description="Restaurant identifier for multi-tenancy")
    order_type: OrderType = OrderType.DINE_IN
    table_id: Optional[str] = Field(None, description="Table ID for dine-in orders (null for takeaway)")
    status: OrderStatus = OrderStatus.DRAFT
    items: List[OrderItem] = Field(..., min_items=1, description="Order items with snapshots")
    total_amount: int = Field(..., ge=0, description="Total order amount in cents (calculated and stored)")


class OrderCreate(OrderBase):
    """Schema for creating a new order."""
    created_by_user_id: str = Field(..., description="User (waiter) who created this order")


class OrderUpdate(BaseModel):
    """
    Schema for updating order details.
    
    Note: Once order is SENT_TO_KITCHEN, items become immutable.
    Only status transitions and item-level status updates allowed.
    """
    status: Optional[OrderStatus] = None
    items: Optional[List[OrderItem]] = None  # Only allowed in DRAFT status
    total_amount: Optional[int] = Field(None, ge=0)


class OrderItemStatusUpdate(BaseModel):
    """Schema for updating individual item status within an order."""
    menu_item_id: str = Field(..., description="Menu item ID to update")
    status: OrderItemStatus = Field(..., description="New status for the item")


class OrderItemCreate(BaseModel):
    """Schema for creating an order item (before snapshots are created)."""
    menu_item_id: str = Field(..., description="Reference to menu item")
    quantity: int = Field(..., ge=1, description="Quantity ordered")
    notes: Optional[str] = Field(None, max_length=500, description="Special instructions")


class OrderCreateRequest(BaseModel):
    """Schema for order creation request from frontend (before validation and snapshots)."""
    order_type: OrderType = OrderType.DINE_IN
    table_id: Optional[str] = Field(None, description="Table ID for dine-in orders")
    items: List[OrderItemCreate] = Field(..., min_items=1, description="Order items")


class OrderInDB(OrderBase):
    """Order model as stored in database."""
    id: str = Field(..., alias="_id")
    order_number: int = Field(..., ge=1, description="Human-readable sequential order number")
    created_by_user_id: str
    created_at: datetime
    sent_to_kitchen_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class OrderResponse(BaseModel):
    """Order data returned to clients."""
    id: str
    restaurant_id: str
    order_number: int
    order_type: OrderType
    table_id: Optional[str]
    table_number: Optional[int] = Field(None, description="Table number (populated if table_id exists)")
    table_location: Optional[str] = Field(None, description="Table location/name (populated if table_id exists)")
    status: OrderStatus
    items: List[OrderItem]
    total_amount: int
    created_by_user_id: str
    created_at: datetime
    sent_to_kitchen_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class OrderSummary(BaseModel):
    """
    Lightweight order summary for list views.
    
    Used in kitchen view and waiter's order list to reduce data transfer.
    """
    id: str
    order_number: int
    table_id: Optional[str]
    status: OrderStatus
    item_count: int
    total_amount: int
    created_at: datetime
    wait_time_minutes: Optional[int] = None  # Calculated field for kitchen view

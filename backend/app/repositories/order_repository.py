"""
Order repository for database operations.

Handles all order-related database queries.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.order import (
    OrderCreate,
    OrderInDB,
    OrderStatus,
    OrderUpdate,
)

logger = logging.getLogger(__name__)


class OrderRepository:
    """Repository for order database operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize order repository.
        
        Args:
            db: MongoDB database instance.
        """
        self.db = db
        self.collection = db.orders

    async def create(self, order: OrderCreate, order_number: int) -> OrderInDB:
        """
        Create a new order in the database.
        
        Args:
            order: Order creation data.
            order_number: Sequential order number (timestamp-based).
            
        Returns:
            OrderInDB: Created order with database ID.
        """
        now = datetime.now(timezone.utc)
        
        order_doc = {
            "restaurant_id": order.restaurant_id,
            "order_type": order.order_type.value,
            "table_id": order.table_id,
            "status": order.status.value,
            "items": [
                {
                    "menu_item_id": item.menu_item_id,
                    "name_snapshot": item.name_snapshot,
                    "price_snapshot": item.price_snapshot,
                    "quantity": item.quantity,
                    "notes": item.notes,
                    "status": item.status.value,
                }
                for item in order.items
            ],
            "total_amount": order.total_amount,
            "order_number": order_number,
            "created_by_user_id": order.created_by_user_id,
            "created_at": now,
            "sent_to_kitchen_at": None,
            "completed_at": None,
        }
        
        result = await self.collection.insert_one(order_doc)
        order_doc["_id"] = str(result.inserted_id)
        
        return OrderInDB(**order_doc)

    async def get_by_id(self, order_id: str) -> Optional[OrderInDB]:
        """
        Get order by ID.
        
        Args:
            order_id: Order's database ID.
            
        Returns:
            OrderInDB or None if not found.
        """
        try:
            doc = await self.collection.find_one({"_id": ObjectId(order_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
                return OrderInDB(**doc)
            return None
        except (ValueError, InvalidId) as e:
            logger.warning(f"Invalid order_id format: {order_id}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_by_id for order_id {order_id}: {e}", exc_info=True)
            return None

    async def get_by_status(
        self,
        restaurant_id: str,
        status: OrderStatus
    ) -> List[OrderInDB]:
        """
        Get all orders with a specific status for a restaurant.
        
        Args:
            restaurant_id: Restaurant identifier.
            status: Order status to filter by.
            
        Returns:
            List of orders with the specified status.
        """
        cursor = self.collection.find({
            "restaurant_id": restaurant_id,
            "status": status.value
        }).sort("sent_to_kitchen_at", 1)  # Sort by when sent to kitchen (oldest first)
        
        orders = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            orders.append(OrderInDB(**doc))
        
        return orders

    async def get_active_orders(
        self,
        restaurant_id: str
    ) -> List[OrderInDB]:
        """
        Get all active orders (SENT_TO_KITCHEN or IN_PROGRESS) for a restaurant.
        
        Args:
            restaurant_id: Restaurant identifier.
            
        Returns:
            List of active orders.
        """
        cursor = self.collection.find({
            "restaurant_id": restaurant_id,
            "status": {
                "$in": [OrderStatus.SENT_TO_KITCHEN.value, OrderStatus.IN_PROGRESS.value]
            }
        }).sort("sent_to_kitchen_at", 1)
        
        orders = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            orders.append(OrderInDB(**doc))
        
        return orders

    async def update_status(
        self,
        order_id: str,
        status: OrderStatus,
        restaurant_id: str
    ) -> Optional[OrderInDB]:
        """
        Update order status.
        
        Args:
            order_id: Order's database ID.
            status: New status value.
            restaurant_id: Restaurant identifier for authorization.
            
        Returns:
            OrderInDB or None if not found or unauthorized.
        """
        try:
            now = datetime.now(timezone.utc)
            update_dict = {
                "status": status.value,
                "updated_at": now,
            }
            
            # Set timestamp based on status transition
            if status == OrderStatus.SENT_TO_KITCHEN:
                update_dict["sent_to_kitchen_at"] = now
            elif status == OrderStatus.COMPLETED:
                update_dict["completed_at"] = now
            
            result = await self.collection.update_one(
                {
                    "_id": ObjectId(order_id),
                    "restaurant_id": restaurant_id  # Authorization check
                },
                {"$set": update_dict}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                return await self.get_by_id(order_id)
            return None
        except (ValueError, InvalidId) as e:
            logger.warning(f"Invalid order_id format in update_status: {order_id}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in update_status for order_id {order_id}: {e}", exc_info=True)
            return None

    async def update(self, order_id: str, update_data: OrderUpdate, restaurant_id: str) -> Optional[OrderInDB]:
        """
        Update order details.
        
        Note: Only allowed for DRAFT orders. Status transitions should use update_status.
        
        Args:
            order_id: Order's database ID.
            update_data: Fields to update.
            restaurant_id: Restaurant identifier for authorization.
            
        Returns:
            OrderInDB or None if not found or unauthorized.
        """
        update_dict = update_data.model_dump(exclude_unset=True)
        
        if not update_dict:
            return await self.get_by_id(order_id)
        
        # Convert enums to values
        if "status" in update_dict and update_dict["status"]:
            update_dict["status"] = update_dict["status"].value
        
        # Convert items if present
        if "items" in update_dict and update_dict["items"]:
            update_dict["items"] = [
                {
                    "menu_item_id": item.menu_item_id,
                    "name_snapshot": item.name_snapshot,
                    "price_snapshot": item.price_snapshot,
                    "quantity": item.quantity,
                    "notes": item.notes,
                    "status": item.status.value if item.status else "pending",
                }
                for item in update_dict["items"]
            ]
        
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        try:
            result = await self.collection.update_one(
                {
                    "_id": ObjectId(order_id),
                    "restaurant_id": restaurant_id  # Authorization check
                },
                {"$set": update_dict}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                return await self.get_by_id(order_id)
            return None
        except (ValueError, InvalidId) as e:
            logger.warning(f"Invalid order_id format in update: {order_id}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in update for order_id {order_id}: {e}", exc_info=True)
            return None

    async def ensure_indexes(self) -> None:
        """Create database indexes for the orders collection."""
        await self.collection.create_index("restaurant_id")
        await self.collection.create_index("status")
        await self.collection.create_index("table_id")
        await self.collection.create_index("order_number")
        await self.collection.create_index([("restaurant_id", 1), ("status", 1)])
        await self.collection.create_index("sent_to_kitchen_at")

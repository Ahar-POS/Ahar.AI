"""
Delivery Order repository for database operations.

Handles all delivery order-related database queries for P&L reporting.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.delivery_order import DeliveryOrderCreate, DeliveryOrderInDB

logger = logging.getLogger(__name__)


class DeliveryOrderRepository:
    """Repository for delivery order database operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize delivery order repository.

        Args:
            db: MongoDB database instance.
        """
        self.db = db
        self.collection = db.delivery_orders

    async def create(self, order: DeliveryOrderCreate) -> DeliveryOrderInDB:
        """
        Create a new delivery order record.

        Args:
            order: Delivery order creation data.

        Returns:
            DeliveryOrderInDB: Created order with database ID.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        order_doc = {
            "order_date": order.order_date,
            "total_inr": float(order.total_inr),
            "promo_discount_inr": float(order.promo_discount_inr),
            "item_discount_inr": float(order.item_discount_inr),
            "tax_gst_inr": float(order.tax_gst_inr),
            "delivery_fee_inr": float(order.delivery_fee_inr),
            "packaging_charge_inr": float(order.packaging_charge_inr),
            "order_channel": order.order_channel.value,
            "restaurant_id": str(order.restaurant_id),
            "created_at": now,
            "updated_at": None,
        }

        try:
            result = await self.collection.insert_one(order_doc)
        except Exception as e:
            logger.exception(
                "Delivery order insert failed: restaurant_id=%s",
                order.restaurant_id,
            )
            raise

        order_doc["_id"] = str(result.inserted_id)
        return DeliveryOrderInDB(**order_doc)

    async def get_by_date_range(
        self,
        restaurant_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[DeliveryOrderInDB]:
        """
        Get delivery orders within a date range for P&L reporting.

        Args:
            restaurant_id: Restaurant identifier.
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            List of delivery orders within the date range.
        """
        cursor = self.collection.find({
            "restaurant_id": restaurant_id,
            "order_date": {
                "$gte": start_date,
                "$lte": end_date
            }
        }).sort("order_date", 1)

        orders = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            orders.append(DeliveryOrderInDB(**doc))

        return orders

    async def bulk_create(self, orders: List[DeliveryOrderCreate]) -> int:
        """
        Bulk insert delivery orders (for data import).

        Args:
            orders: List of delivery orders to create.

        Returns:
            Number of orders inserted.
        """
        if not orders:
            return 0

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        order_docs = []
        for order in orders:
            order_docs.append({
                "order_date": order.order_date,
                "total_inr": float(order.total_inr),
                "promo_discount_inr": float(order.promo_discount_inr),
                "item_discount_inr": float(order.item_discount_inr),
                "tax_gst_inr": float(order.tax_gst_inr),
                "delivery_fee_inr": float(order.delivery_fee_inr),
                "packaging_charge_inr": float(order.packaging_charge_inr),
                "order_channel": order.order_channel.value,
                "restaurant_id": str(order.restaurant_id),
                "created_at": now,
                "updated_at": None,
            })

        try:
            result = await self.collection.insert_many(order_docs, ordered=False)
            return len(result.inserted_ids)
        except Exception as e:
            logger.exception("Bulk delivery order insert failed")
            raise

    async def ensure_indexes(self) -> None:
        """Create database indexes for the delivery_orders collection."""
        await self.collection.create_index("restaurant_id")
        await self.collection.create_index("order_date")
        await self.collection.create_index("order_channel")
        await self.collection.create_index([("restaurant_id", 1), ("order_date", 1)])

#!/usr/bin/env python3
"""
Test script to verify new order creation works with all schema fixes.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.repositories.order_repository import OrderRepository
from app.models.order import OrderCreate, OrderItemCreate, OrderType, OrderStatus, OrderItemStatus


async def test_order_creation():
    """Test creating a new order with the updated schema."""

    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.DB_NAME]

    repo = OrderRepository(db)

    # Get a menu item for testing
    menu_item = await db.menu_items.find_one()
    if not menu_item:
        print("❌ No menu items found in database")
        return False

    print(f"✓ Found menu item: {menu_item.get('name', 'Unknown')}")

    # Create test order
    order_data = OrderCreate(
        restaurant_id="REST001",
        order_type=OrderType.DINE_IN,
        table_id="TBL05",
        items=[
            OrderItemCreate(
                menu_item_id=str(menu_item["_id"]),
                name_snapshot=menu_item["name"],
                price_snapshot=menu_item["price_inr"],
                quantity=2,
                notes="Test order",
                status=OrderItemStatus.PENDING
            )
        ],
        total_amount=menu_item["price_inr"] * 2,
        created_by_user_id="USER001",
        status=OrderStatus.DRAFT
    )

    # Get next order number
    last_order = await db.orders.find_one(sort=[("order_number", -1)])
    order_number = (last_order["order_number"] + 1) if last_order else 1

    print(f"✓ Creating order with order_number: {order_number}")

    try:
        # Create order
        created_order = await repo.create(order_data, order_number)

        print(f"\n{'='*60}")
        print(f"✅ ORDER CREATED SUCCESSFULLY")
        print(f"{'='*60}")
        print(f"Order ID: {created_order.order_id}")
        print(f"Order Number: {created_order.order_number}")
        print(f"Order Date: {created_order.order_date}")
        print(f"Order Time: {created_order.order_time}")
        print(f"Order Hour: {created_order.order_hour}")
        print(f"Weekday: {created_order.order_weekday}")
        print(f"Is Weekend: {created_order.is_weekend}")
        print(f"Order Type: {created_order.order_type}")
        print(f"Table ID: {created_order.table_id}")
        print(f"Staff ID: {created_order.staff_id}")
        print(f"Total Amount: ₹{created_order.total_amount / 100:.2f}")
        print(f"Status: {created_order.status}")
        print(f"{'='*60}")

        # Verify all required fields are present
        required_fields = [
            "order_id", "order_number", "order_date", "order_time",
            "order_hour", "order_weekday", "is_weekend", "order_type",
            "staff_id", "status", "total_amount", "created_at"
        ]

        missing_fields = []
        for field in required_fields:
            if not hasattr(created_order, field) or getattr(created_order, field) is None:
                missing_fields.append(field)

        if missing_fields:
            print(f"⚠️  Missing fields: {', '.join(missing_fields)}")
            return False

        print(f"\n✅ All required fields present")
        print(f"✅ Order schema matches imported data schema")

        # Clean up test order
        await db.orders.delete_one({"_id": created_order.id})
        print(f"\n✓ Cleaned up test order")

        return True

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ ORDER CREATION FAILED")
        print(f"{'='*60}")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        client.close()


if __name__ == "__main__":
    success = asyncio.run(test_order_creation())
    sys.exit(0 if success else 1)

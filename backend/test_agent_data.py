"""
Generate Test Data for Agent Testing

Creates orders, inventory scenarios with intentional issues:
- Revenue anomalies (spikes and drops)
- Low inventory levels (trigger stockout alerts)
- High food cost items (>35%)
- Low margin menu items (<25%)
"""

import asyncio
from datetime import datetime, timedelta
import random
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# MongoDB connection
# Use mongodb service name in Docker, localhost outside
import os
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://mongodb:27017")
DB_NAME = "ahar_pos"


async def generate_test_data():
    """Generate test data with intentional issues"""
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    print("=" * 70)
    print("GENERATING TEST DATA FOR AGENT TESTING")
    print("=" * 70)
    print()

    # Get existing data
    menu_items = await db.menu_items.find({}).to_list(length=None)
    inventory_items = await db.raw_material_inventory.find({}).to_list(length=None)

    if not menu_items:
        print("❌ No menu items found. Please load menu data first.")
        return

    # Date range: Jan 29 - Feb 24, 2026 (adding to existing data)
    start_date = datetime(2026, 1, 29)
    end_date = datetime(2026, 2, 24)

    print(f"📅 Generating orders from {start_date.date()} to {end_date.date()}")
    print()

    # === SCENARIO 1: Revenue Anomaly ===
    print("📊 SCENARIO 1: Revenue Anomaly (Feb 20 - spike, Feb 22 - drop)")

    orders_to_insert = []
    current_date = start_date

    while current_date <= end_date:
        # Normal days: 5-8 orders
        base_orders = random.randint(5, 8)

        # Feb 20: Revenue spike (3x normal)
        if current_date.date() == datetime(2026, 2, 20).date():
            base_orders = 25
            print(f"   💥 Feb 20: Spike - {base_orders} orders (3x normal)")

        # Feb 22: Revenue drop (50% of normal)
        elif current_date.date() == datetime(2026, 2, 22).date():
            base_orders = 3
            print(f"   📉 Feb 22: Drop - {base_orders} orders (50% of normal)")

        # Generate orders for this day
        for _ in range(base_orders):
            order_time = current_date + timedelta(
                hours=random.randint(11, 21),
                minutes=random.randint(0, 59)
            )

            # Select 1-3 random menu items
            num_items = random.randint(1, 3)
            selected_items = random.sample(menu_items, num_items)

            order_items = []
            total_amount = 0

            for item in selected_items:
                quantity = random.randint(1, 2)
                price = item.get("price", 30000)  # Default ₹300

                order_items.append({
                    "menu_item_id": item["menu_item_id"],
                    "name_snapshot": item["name"],
                    "price_snapshot": price,
                    "quantity": quantity,
                    "notes": None,
                    "status": "ready"
                })
                total_amount += price * quantity

            # Generate unique order_id
            order_id = f"ORD{order_time.strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

            order = {
                "order_id": order_id,
                "restaurant_id": "RSTDEV001",
                "order_type": random.choice(["dine_in", "takeaway"]),
                "table_id": f"T{random.randint(1, 10):02d}" if random.random() > 0.3 else None,
                "status": "completed",
                "items": order_items,
                "total_amount": total_amount,
                "order_date": order_time,
                "created_at": order_time,
                "updated_at": order_time,
                "created_by_user_id": "STAFFDEV001"
            }

            orders_to_insert.append(order)

        current_date += timedelta(days=1)

    # Insert orders
    if orders_to_insert:
        result = await db.orders.insert_many(orders_to_insert)
        print(f"   ✅ Inserted {len(result.inserted_ids)} orders")
    print()

    # === SCENARIO 2: Low Inventory (Trigger Stockout) ===
    print("📦 SCENARIO 2: Low Inventory Levels (Trigger Urgent Reorders)")

    # Select 5 critical items to set low stock
    critical_items = [
        "RM001",  # Chicken breast
        "RM002",  # Lettuce
        "RM010",  # Tomatoes
        "RM015",  # Cheese
        "RM020"   # Bread
    ]

    for material_id in critical_items:
        # Set stock to 10% of reorder level (critical low)
        item = await db.raw_material_inventory.find_one({"material_id": material_id})
        if item:
            reorder_level = item.get("reorder_level", 1000)
            new_stock = reorder_level * 0.1  # 10% of reorder level

            await db.raw_material_inventory.update_one(
                {"material_id": material_id},
                {
                    "$set": {
                        "current_stock": new_stock,
                        "last_updated": datetime.utcnow()
                    }
                }
            )
            print(f"   ⚠️  {material_id}: Stock set to {new_stock:.0f} (Reorder: {reorder_level})")

    print(f"   ✅ Set 5 items to critical low stock")
    print()

    # === SCENARIO 3: High Food Cost Items ===
    print("💰 SCENARIO 3: High Food Cost Items (>35% target)")

    # Increase ingredient costs to push food cost % above 35%
    expensive_ingredients = ["RM001", "RM015", "RM025", "RM030"]

    for material_id in expensive_ingredients:
        item = await db.raw_material_inventory.find_one({"material_id": material_id})
        if item:
            current_cost = item.get("unit_cost_inr", 1000)
            new_cost = int(current_cost * 1.5)  # Increase by 50%

            await db.raw_material_inventory.update_one(
                {"material_id": material_id},
                {
                    "$set": {
                        "unit_cost_inr": new_cost,
                        "last_updated": datetime.utcnow()
                    }
                }
            )
            print(f"   💸 {material_id}: Cost increased {current_cost/100:.2f} → {new_cost/100:.2f} INR")

    print(f"   ✅ Increased costs on 4 ingredients")
    print()

    # === SCENARIO 4: Low Margin Menu Items ===
    print("📉 SCENARIO 4: Low Margin Items (Create loss-leaders)")

    # Lower prices on 2 items to create low margins
    low_margin_items = ["MENU001", "MENU005"]

    for menu_item_id in low_margin_items:
        item = await db.menu_items.find_one({"menu_item_id": menu_item_id})
        if item:
            current_price = item.get("price", 30000)
            new_price = int(current_price * 0.7)  # Reduce by 30%

            await db.menu_items.update_one(
                {"menu_item_id": menu_item_id},
                {
                    "$set": {
                        "price": new_price,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            print(f"   📉 {menu_item_id} ({item['name']}): Price {current_price/100:.2f} → {new_price/100:.2f} INR")

    print(f"   ✅ Created 2 low-margin items")
    print()

    # === SCENARIO 5: Expiring Items ===
    print("⏰ SCENARIO 5: Expiring Perishables")

    # Set expiry dates for perishable items
    perishables = ["RM002", "RM010", "RM012"]  # Lettuce, Tomatoes, etc.

    for material_id in perishables:
        # Set to expire in 2 days
        expiry_date = datetime.utcnow() + timedelta(days=2)

        await db.raw_material_inventory.update_one(
            {"material_id": material_id},
            {
                "$set": {
                    "expiry_date": expiry_date,
                    "is_perishable": "Yes",
                    "last_updated": datetime.utcnow()
                }
            }
        )
        print(f"   ⏰ {material_id}: Expires in 2 days ({expiry_date.date()})")

    print(f"   ✅ Set 3 items to expire soon")
    print()

    # === Summary ===
    print("=" * 70)
    print("TEST DATA GENERATION COMPLETE")
    print("=" * 70)
    print()
    print("Expected Agent Alerts:")
    print("  🤖 INVENTORY AGENT:")
    print("     - 5 URGENT reorder alerts (critical low stock)")
    print("     - 3 perishable expiry warnings")
    print()
    print("  💰 FINANCIAL AGENT:")
    print("     - Revenue anomaly: Feb 20 spike (+200%)")
    print("     - Revenue anomaly: Feb 22 drop (-50%)")
    print("     - High food cost alert (>35% from price increases)")
    print("     - Low margin items alert (2 items <25% margin)")
    print()
    print("Trigger agents to see alerts:")
    print("  curl -X POST http://localhost:8000/api/v1/health/trigger-agent/inventory")
    print("  curl -X POST http://localhost:8000/api/v1/health/trigger-agent/financial")
    print()

    client.close()


if __name__ == "__main__":
    asyncio.run(generate_test_data())

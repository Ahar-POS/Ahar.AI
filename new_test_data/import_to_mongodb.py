"""
Import Test Data to MongoDB

Imports all CSV files from new_test_data/ into MongoDB collections
with proper schema transformation for embedded documents.
"""

import pandas as pd
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import sys
import numpy as np

# MongoDB connection
import os
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "ahar_pos")

def clean_doc(doc):
    """Replace NaN/NaT values with None for MongoDB compatibility"""
    cleaned = {}
    for key, value in doc.items():
        if pd.isna(value):
            cleaned[key] = None
        elif isinstance(value, (pd.Timestamp, datetime)):
            cleaned[key] = value
        else:
            cleaned[key] = value
    return cleaned

async def import_test_data():
    """Import all test data CSV files to MongoDB"""

    print("=" * 80)
    print("IMPORTING TEST DATA TO MONGODB")
    print("=" * 80)

    # Set working directory to script location
    import os
    from pathlib import Path
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    print(f"Working directory: {os.getcwd()}")

    # Connect to MongoDB
    print("\n1. Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]

    try:
        await db.command('ping')
        print("✓ Connected to MongoDB")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        print("\nPlease ensure MongoDB is running:")
        print("  docker compose up -d")
        print("  OR")
        print("  mongod --dbpath /path/to/data")
        return

    # Clear existing collections
    print("\n2. Clearing existing test collections...")
    collections_to_clear = [
        'menu_items', 'recipe_bom', 'raw_material_inventory',
        'orders', 'stock_movements', 'suppliers',
        'promotions', 'purchase_history', 'wastage_log', 'stockout_log'
    ]

    for coll in collections_to_clear:
        try:
            await db[coll].delete_many({})
            print(f"✓ Cleared {coll}")
        except:
            print(f"  {coll} (new collection)")

    # Import Menu Items
    print("\n3. Importing menu items...")
    menu_df = pd.read_csv("menu_items.csv")
    menu_df['tags'] = menu_df['tags'].str.split(',')  # Convert to array
    menu_df['created_at'] = pd.to_datetime(menu_df['created_at'])
    menu_df['updated_at'] = menu_df['created_at']

    menu_docs = menu_df.to_dict('records')
    await db.menu_items.insert_many(menu_docs)
    print(f"✓ Imported {len(menu_docs)} menu items")

    # Create indexes
    await db.menu_items.create_index("menu_item_id", unique=True)
    await db.menu_items.create_index("category")
    await db.menu_items.create_index("is_available")
    print("✓ Created indexes on menu_items")

    # Import Recipe BOM (as embedded documents)
    print("\n4. Importing recipe BOM...")
    recipe_df = pd.read_csv("recipe_bom.csv")

    # Group by menu_item_id and create embedded ingredients
    recipes = []
    for menu_item_id, group in recipe_df.groupby('menu_item_id'):
        recipe_doc = {
            'menu_item_id': menu_item_id,
            'menu_item_name': group.iloc[0]['menu_item_name'],
            'ingredients': [
                {
                    'material_id': row['material_id'],
                    'material_name': row['material_name'],
                    'quantity_per_serving': float(row['quantity_per_serving']),
                    'unit': row['unit'],
                    'is_critical': bool(row['is_critical'])
                }
                for _, row in group.iterrows()
            ],
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        recipes.append(recipe_doc)

    await db.recipe_bom.insert_many(recipes)
    print(f"✓ Imported {len(recipes)} recipes ({len(recipe_df)} ingredients)")

    # Create indexes
    await db.recipe_bom.create_index("menu_item_id", unique=True)
    await db.recipe_bom.create_index("ingredients.material_id")
    print("✓ Created indexes on recipe_bom")

    # Import Raw Material Inventory
    print("\n5. Importing raw material inventory...")
    inventory_df = pd.read_csv("raw_material_inventory.csv")
    inventory_df['created_at'] = pd.to_datetime(inventory_df['created_at'])
    inventory_df['updated_at'] = inventory_df['created_at']
    if 'last_restock_date' in inventory_df.columns:
        inventory_df['last_restock_date'] = pd.to_datetime(inventory_df['last_restock_date'])

    # Replace NaT with None for MongoDB compatibility
    inventory_df = inventory_df.where(pd.notna(inventory_df), None)

    inventory_docs = inventory_df.to_dict('records')
    await db.raw_material_inventory.insert_many(inventory_docs)
    print(f"✓ Imported {len(inventory_docs)} raw materials")

    # Create indexes
    await db.raw_material_inventory.create_index("material_id", unique=True)
    await db.raw_material_inventory.create_index("category")
    await db.raw_material_inventory.create_index("is_perishable")
    await db.raw_material_inventory.create_index("current_stock")
    print("✓ Created indexes on raw_material_inventory")

    # Import Orders (with embedded items)
    print("\n6. Importing orders...")
    orders_df = pd.read_csv("orders.csv")
    items_df = pd.read_csv("order_line_items.csv")

    # Convert dates
    orders_df['order_date'] = pd.to_datetime(orders_df['order_date'])
    orders_df['created_at'] = pd.to_datetime(orders_df['created_at'])
    if 'sent_to_kitchen_at' in orders_df.columns:
        orders_df['sent_to_kitchen_at'] = pd.to_datetime(orders_df['sent_to_kitchen_at'])
    if 'completed_at' in orders_df.columns:
        orders_df['completed_at'] = pd.to_datetime(orders_df['completed_at'])

    # Replace NaT with None for MongoDB compatibility
    orders_df = orders_df.where(pd.notna(orders_df), None)

    # Process orders with embedded items
    order_docs = []
    for _, order in orders_df.iterrows():
        order_doc = clean_doc(order.to_dict())

        # Get items for this order
        order_items = items_df[items_df['order_id'] == order['order_id']]
        order_doc['items'] = [
            {
                'menu_item_id': item['menu_item_id'],
                'name_snapshot': item['menu_item_name'],  # Use name_snapshot convention
                'quantity': int(item['quantity']),
                'price_snapshot': int(item['price_snapshot']),
                'notes': '' if pd.isna(item.get('notes')) else str(item.get('notes', '')),
                'item_status': item['item_status']
            }
            for _, item in order_items.iterrows()
        ]

        order_docs.append(order_doc)

    # Insert in batches (MongoDB has 16MB document limit)
    batch_size = 100
    for i in range(0, len(order_docs), batch_size):
        batch = order_docs[i:i+batch_size]
        await db.orders.insert_many(batch)
        print(f"  Imported orders {i+1}-{min(i+batch_size, len(order_docs))} / {len(order_docs)}")

    print(f"✓ Imported {len(order_docs)} orders with {len(items_df)} items")

    # Create indexes
    await db.orders.create_index("order_id", unique=True)
    await db.orders.create_index("order_date")
    await db.orders.create_index("status")
    await db.orders.create_index([("order_date", 1), ("order_hour", 1)])
    print("✓ Created indexes on orders")

    # Import Stock Movements
    print("\n7. Importing stock movements...")
    movements_df = pd.read_csv("stock_movement_log.csv")
    movements_df['movement_date'] = pd.to_datetime(movements_df['movement_date'])
    movements_df['created_at'] = pd.to_datetime(movements_df['created_at'])

    # Replace NaT with None for MongoDB compatibility
    movements_df = movements_df.where(pd.notna(movements_df), None)

    movements_docs = movements_df.to_dict('records')
    await db.stock_movements.insert_many(movements_docs)
    print(f"✓ Imported {len(movements_docs)} stock movements")

    # Create indexes
    await db.stock_movements.create_index("movement_id", unique=True)
    await db.stock_movements.create_index("material_id")
    await db.stock_movements.create_index("movement_type")
    await db.stock_movements.create_index("movement_date")
    print("✓ Created indexes on stock_movements")

    # Import Suppliers
    print("\n8. Importing suppliers...")
    supplier_df = pd.read_csv("supplier_master.csv")
    supplier_df['created_at'] = pd.to_datetime(supplier_df['created_at'])

    supplier_docs = supplier_df.to_dict('records')
    await db.suppliers.insert_many(supplier_docs)
    print(f"✓ Imported {len(supplier_docs)} suppliers")

    await db.suppliers.create_index("supplier_id", unique=True)
    print("✓ Created indexes on suppliers")

    # Import Promotions (new collection)
    print("\n9. Importing promotions...")
    try:
        promotions_df = pd.read_csv("promotions.csv")
        promotions_df['start_date'] = pd.to_datetime(promotions_df['start_date'])
        promotions_df['end_date'] = pd.to_datetime(promotions_df['end_date'])
        promotions_df['created_at'] = datetime.utcnow()

        promotions_docs = promotions_df.to_dict('records')
        if promotions_docs:
            await db.promotions.insert_many(promotions_docs)
            await db.promotions.create_index("promo_id", unique=True)
            await db.promotions.create_index([("start_date", 1), ("end_date", 1)])
            print(f"✓ Imported {len(promotions_docs)} promotions")
        else:
            print("  (No promotions to import)")
    except FileNotFoundError:
        print("  (promotions.csv not found - skipping)")

    # Import Purchase History (new collection)
    print("\n10. Importing purchase history...")
    try:
        purchases_df = pd.read_csv("purchase_history.csv")
        purchases_df['purchase_date'] = pd.to_datetime(purchases_df['purchase_date'])
        purchases_df['created_at'] = datetime.utcnow()

        purchases_docs = purchases_df.to_dict('records')
        if purchases_docs:
            # Import in batches
            batch_size = 100
            for i in range(0, len(purchases_docs), batch_size):
                batch = purchases_docs[i:i+batch_size]
                await db.purchase_history.insert_many(batch)

            await db.purchase_history.create_index("purchase_id", unique=True)
            await db.purchase_history.create_index("material_id")
            await db.purchase_history.create_index("purchase_date")
            print(f"✓ Imported {len(purchases_docs)} purchase orders")
        else:
            print("  (No purchase history to import)")
    except FileNotFoundError:
        print("  (purchase_history.csv not found - skipping)")

    # Import Wastage Log (new collection)
    print("\n11. Importing wastage log...")
    try:
        wastage_df = pd.read_csv("wastage_log.csv")
        wastage_df['date'] = pd.to_datetime(wastage_df['date'])
        wastage_df['created_at'] = datetime.utcnow()

        wastage_docs = wastage_df.to_dict('records')
        if wastage_docs:
            # Import in batches
            batch_size = 100
            for i in range(0, len(wastage_docs), batch_size):
                batch = wastage_docs[i:i+batch_size]
                await db.wastage_log.insert_many(batch)

            await db.wastage_log.create_index("material_id")
            await db.wastage_log.create_index("date")
            await db.wastage_log.create_index("reason")
            print(f"✓ Imported {len(wastage_docs)} wastage records")
        else:
            print("  (No wastage logs to import)")
    except FileNotFoundError:
        print("  (wastage_log.csv not found - skipping)")

    # Import Stock-out Log (new collection)
    print("\n12. Importing stock-out log...")
    try:
        stockout_df = pd.read_csv("stockout_log.csv")
        stockout_df['date'] = pd.to_datetime(stockout_df['date'])
        stockout_df['created_at'] = datetime.utcnow()

        stockout_docs = stockout_df.to_dict('records')
        if stockout_docs:
            await db.stockout_log.insert_many(stockout_docs)
            await db.stockout_log.create_index("material_id")
            await db.stockout_log.create_index("date")
            print(f"✓ Imported {len(stockout_docs)} stock-out events")
        else:
            print("  (No stock-out logs to import)")
    except FileNotFoundError:
        print("  (stockout_log.csv not found - skipping)")

    # Verify import
    print("\n" + "=" * 80)
    print("IMPORT VERIFICATION")
    print("=" * 80)

    collections = {
        'menu_items': await db.menu_items.count_documents({}),
        'recipe_bom': await db.recipe_bom.count_documents({}),
        'raw_material_inventory': await db.raw_material_inventory.count_documents({}),
        'orders': await db.orders.count_documents({}),
        'stock_movements': await db.stock_movements.count_documents({}),
        'suppliers': await db.suppliers.count_documents({}),
        'promotions': await db.promotions.count_documents({}),
        'purchase_history': await db.purchase_history.count_documents({}),
        'wastage_log': await db.wastage_log.count_documents({}),
        'stockout_log': await db.stockout_log.count_documents({})
    }

    for coll, count in collections.items():
        print(f"✓ {coll}: {count:,} documents")

    print("\n" + "=" * 80)
    print("🎉 IMPORT COMPLETE!")
    print("=" * 80)
    print("\nYou can now:")
    print("  1. Verify in MongoDB:")
    print("     mongosh")
    print("     use ahar_pos")
    print("     db.orders.countDocuments()")
    print("     db.recipe_bom.findOne()")
    print("\n  2. Start Week 2 implementation (Demand Forecaster)")
    print("\n  3. Start the backend server:")
    print("     cd backend")
    print("     uvicorn app.main:app --reload --port 8000")
    print("=" * 80)

    client.close()

if __name__ == "__main__":
    asyncio.run(import_test_data())

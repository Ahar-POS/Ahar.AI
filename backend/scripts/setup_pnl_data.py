#!/usr/bin/env python3
"""
P&L Data Setup Script

Populates MongoDB with required data for detailed P&L generation:
1. Default restaurant settings (commissions, salaries, OPEX budgets)
2. Packaging materials (boxes, bags, stickers with costs)
3. Packaging BOM (links menu items to packaging)
4. Fixed assets (equipment, brand for depreciation)
5. Sample stock movements (wastage, staff meals for past 4 months)

Safe to re-run - checks for existing data before inserting.

Usage:
    python setup_pnl_data.py [restaurant_id]
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import random

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError


# MongoDB connection
def get_mongodb_client():
    """Get MongoDB client"""
    mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    try:
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.server_info()
        return client
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        sys.exit(1)


def get_database(client):
    """Get database"""
    db_name = os.getenv('DB_NAME', 'ahar_pos')
    return client[db_name]


def create_restaurant_settings(db, restaurant_id: str):
    """Create default restaurant settings"""
    collection = db.restaurant_settings

    # Check if already exists
    existing = collection.find_one({"restaurant_id": restaurant_id})
    if existing:
        print(f"✓ Restaurant settings already exist for '{restaurant_id}'")
        return existing

    # Create default settings based on cloud_kitchen_pl.xlsx
    settings = {
        "restaurant_id": restaurant_id,
        "platform_settings": {
            "zomato_commission_rate": 0.23,
            "swiggy_commission_rate": 0.23,
            "gst_rate": 0.05,
            "cancellation_rate": 0.015
        },
        "role_salaries": {
            "cook": 5000000,  # ₹50,000 in paise
            "helper": 2500000,  # ₹25,000
            "packing_staff": 2200000,  # ₹22,000
            "supervisor": 6000000,  # ₹60,000
            "manager": 8000000,  # ₹80,000
            "waiter": 2000000,  # ₹20,000
            "admin": 4000000  # ₹40,000
        },
        "pf_esic_settings": {
            "pf_employer_rate": 0.12,
            "esic_employer_rate": 0.0175
        },
        "overtime_settings": {
            "cook": 500000,  # ₹5,000
            "helper": 300000,  # ₹3,000
            "packing_staff": 300000,  # ₹3,000
            "supervisor": 500000,  # ₹5,000
            "manager": 0,
            "waiter": 200000,  # ₹2,000
            "admin": 0
        },
        "occupancy_costs": {
            "rent": 3200000,  # ₹32,000
            "electricity": 1800000,  # ₹18,000
            "water": 300000,  # ₹3,000
            "internet": 200000  # ₹2,000
        },
        "technology_costs": {
            "pos_software": 1000000,  # ₹10,000
            "platform_subscriptions": 200000,  # ₹2,000
            "menu_photography_amortized": 150000  # ₹1,500
        },
        "marketing_budgets": {
            "zomato_ads": 2500000,  # ₹25,000
            "swiggy_ads": 1000000,  # ₹10,000
            "social_media": 800000,  # ₹8,000
            "influencer": 500000,  # ₹5,000
            "self_funded_discounts": 1500000  # ₹15,000
        },
        "general_admin_costs": {
            "accounting": 500000,  # ₹5,000
            "legal_compliance": 200000,  # ₹2,000
            "insurance": 300000,  # ₹3,000
            "cleaning_supplies": 400000,  # ₹4,000
            "pest_control": 150000,  # ₹1,500
            "repairs_maintenance": 300000,  # ₹3,000
            "gas_lpg": 600000,  # ₹6,000
            "office_supplies": 100000,  # ₹1,000
            "miscellaneous": 300000  # ₹3,000
        },
        "depreciation_amortization": {
            "equipment_depreciation": 1500000,  # ₹15,000
            "brand_amortization": 200000  # ₹2,000
        },
        "finance_costs": {
            "loan_interest": 800000,  # ₹8,000
            "bank_charges": 150000  # ₹1,500
        },
        "tax_settings": {
            "presumptive_tax_rate": 0.26
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = collection.insert_one(settings)
    print(f"✓ Created restaurant settings for '{restaurant_id}'")
    return collection.find_one({"_id": result.inserted_id})


def create_packaging_materials(db):
    """Create packaging materials inventory"""
    collection = db.packaging_materials

    materials = [
        # PRIMARY PACKAGING
        {
            "packaging_id": "PKG001",
            "packaging_name": "Custom Sandwich Box",
            "category": "PRIMARY",
            "unit_cost_inr": 1000,  # ₹10 in paise
            "unit": "Piece",
            "supplier_id": "SUP008",
            "description": "Custom printed kraft boxes for sandwiches",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "packaging_id": "PKG002",
            "packaging_name": "Wrap Container",
            "category": "PRIMARY",
            "unit_cost_inr": 900,  # ₹9 in paise
            "unit": "Piece",
            "supplier_id": "SUP008",
            "description": "Food-safe wrap containers",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "packaging_id": "PKG003",
            "packaging_name": "Bowl with Lid",
            "category": "PRIMARY",
            "unit_cost_inr": 1200,  # ₹12 in paise
            "unit": "Piece",
            "supplier_id": "SUP008",
            "description": "Microwave-safe bowls for rice/noodles",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "packaging_id": "PKG004",
            "packaging_name": "Beverage Cup with Lid",
            "category": "PRIMARY",
            "unit_cost_inr": 600,  # ₹6 in paise
            "unit": "Piece",
            "supplier_id": "SUP008",
            "description": "Disposable cups for beverages",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "packaging_id": "PKG005",
            "packaging_name": "Dessert Container",
            "category": "PRIMARY",
            "unit_cost_inr": 800,  # ₹8 in paise
            "unit": "Piece",
            "supplier_id": "SUP008",
            "description": "Small containers for desserts",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        # SECONDARY PACKAGING
        {
            "packaging_id": "PKG006",
            "packaging_name": "Delivery Bag",
            "category": "SECONDARY",
            "unit_cost_inr": 500,  # ₹5 in paise
            "unit": "Piece",
            "supplier_id": "SUP008",
            "description": "Branded delivery bags",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "packaging_id": "PKG007",
            "packaging_name": "Tissue Paper",
            "category": "SECONDARY",
            "unit_cost_inr": 100,  # ₹1 in paise
            "unit": "Piece",
            "supplier_id": "SUP008",
            "description": "Napkins and tissue",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "packaging_id": "PKG008",
            "packaging_name": "Cutlery Set",
            "category": "SECONDARY",
            "unit_cost_inr": 300,  # ₹3 in paise
            "unit": "Set",
            "supplier_id": "SUP008",
            "description": "Fork, spoon, knife set",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        # LABELS
        {
            "packaging_id": "PKG009",
            "packaging_name": "Tamper Seal Sticker",
            "category": "LABELS",
            "unit_cost_inr": 50,  # ₹0.50 in paise
            "unit": "Piece",
            "supplier_id": "SUP008",
            "description": "Food safety tamper seals",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "packaging_id": "PKG010",
            "packaging_name": "Brand Logo Sticker",
            "category": "LABELS",
            "unit_cost_inr": 80,  # ₹0.80 in paise
            "unit": "Piece",
            "supplier_id": "SUP008",
            "description": "Branded stickers",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]

    inserted_count = 0
    for material in materials:
        try:
            existing = collection.find_one({"packaging_id": material["packaging_id"]})
            if not existing:
                collection.insert_one(material)
                inserted_count += 1
        except DuplicateKeyError:
            pass

    print(f"✓ Created {inserted_count} packaging materials ({len(materials) - inserted_count} already existed)")


def create_packaging_bom(db):
    """Create packaging BOM for menu items"""
    collection = db.packaging_bom
    menu_collection = db.menu_items

    # Get all menu items
    menu_items = list(menu_collection.find({}))
    if not menu_items:
        print("⚠ No menu items found, skipping packaging BOM creation")
        return

    bom_entries = []

    for item in menu_items:
        menu_id = item.get("_id")
        category = item.get("category", "")
        tags = item.get("tags", [])

        # Determine packaging based on category and type
        if "Main Course" in category or "Burger" in item.get("name", ""):
            # Sandwiches/Burgers use box
            bom_entries.append({
                "menu_item_id": str(menu_id),
                "packaging_material_id": "PKG001",  # Sandwich Box
                "quantity_per_serving": 1,
                "is_critical": True
            })
        elif "Wrap" in item.get("name", ""):
            # Wraps use container
            bom_entries.append({
                "menu_item_id": str(menu_id),
                "packaging_material_id": "PKG002",  # Wrap Container
                "quantity_per_serving": 1,
                "is_critical": True
            })
        elif "Rice" in item.get("name", "") or "Noodles" in item.get("name", "") or "Dosa" in item.get("name", ""):
            # Rice/Noodles use bowl
            bom_entries.append({
                "menu_item_id": str(menu_id),
                "packaging_material_id": "PKG003",  # Bowl
                "quantity_per_serving": 1,
                "is_critical": True
            })
        elif "Beverage" in category:
            # Beverages use cup
            bom_entries.append({
                "menu_item_id": str(menu_id),
                "packaging_material_id": "PKG004",  # Cup
                "quantity_per_serving": 1,
                "is_critical": True
            })
        elif "Dessert" in category:
            # Desserts use small container
            bom_entries.append({
                "menu_item_id": str(menu_id),
                "packaging_material_id": "PKG005",  # Dessert Container
                "quantity_per_serving": 1,
                "is_critical": True
            })
        else:
            # Default to sandwich box
            bom_entries.append({
                "menu_item_id": str(menu_id),
                "packaging_material_id": "PKG001",  # Sandwich Box
                "quantity_per_serving": 1,
                "is_critical": True
            })

        # All items get secondary packaging
        bom_entries.append({
            "menu_item_id": str(menu_id),
            "packaging_material_id": "PKG006",  # Delivery Bag
            "quantity_per_serving": 1,
            "is_critical": False
        })
        bom_entries.append({
            "menu_item_id": str(menu_id),
            "packaging_material_id": "PKG007",  # Tissue
            "quantity_per_serving": 2,
            "is_critical": False
        })
        bom_entries.append({
            "menu_item_id": str(menu_id),
            "packaging_material_id": "PKG009",  # Tamper Seal
            "quantity_per_serving": 1,
            "is_critical": True
        })
        bom_entries.append({
            "menu_item_id": str(menu_id),
            "packaging_material_id": "PKG010",  # Brand Sticker
            "quantity_per_serving": 1,
            "is_critical": False
        })

        # Main courses get cutlery
        if "Main Course" in category or "Starters" in category:
            bom_entries.append({
                "menu_item_id": str(menu_id),
                "packaging_material_id": "PKG008",  # Cutlery
                "quantity_per_serving": 1,
                "is_critical": False
            })

    # Insert BOM entries
    inserted_count = 0
    for entry in bom_entries:
        entry["created_at"] = datetime.utcnow()
        entry["updated_at"] = datetime.utcnow()

        existing = collection.find_one({
            "menu_item_id": entry["menu_item_id"],
            "packaging_material_id": entry["packaging_material_id"]
        })
        if not existing:
            collection.insert_one(entry)
            inserted_count += 1

    print(f"✓ Created {inserted_count} packaging BOM entries ({len(bom_entries) - inserted_count} already existed)")


def create_fixed_assets(db):
    """Create fixed assets register"""
    collection = db.fixed_assets

    assets = [
        {
            "asset_id": "FA001",
            "asset_name": "Commercial Grill",
            "category": "EQUIPMENT",
            "purchase_cost_inr": 20000000,  # ₹200,000 in paise
            "useful_life_months": 60,  # 5 years
            "purchase_date": datetime(2024, 1, 1),
            "description": "Heavy-duty commercial grill for sandwiches",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "asset_id": "FA002",
            "asset_name": "Deep Fryer",
            "category": "EQUIPMENT",
            "purchase_cost_inr": 8000000,  # ₹80,000 in paise
            "useful_life_months": 60,
            "purchase_date": datetime(2024, 1, 1),
            "description": "Commercial deep fryer",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "asset_id": "FA003",
            "asset_name": "Commercial Refrigerator",
            "category": "EQUIPMENT",
            "purchase_cost_inr": 6000000,  # ₹60,000 in paise
            "useful_life_months": 60,
            "purchase_date": datetime(2024, 1, 1),
            "description": "Walk-in refrigerator for ingredients",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "asset_id": "FA004",
            "asset_name": "SS Work Tables",
            "category": "EQUIPMENT",
            "purchase_cost_inr": 4000000,  # ₹40,000 in paise
            "useful_life_months": 60,
            "purchase_date": datetime(2024, 1, 1),
            "description": "Stainless steel work tables",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "asset_id": "FA005",
            "asset_name": "Kitchen Equipment (Misc)",
            "category": "EQUIPMENT",
            "purchase_cost_inr": 32000000,  # ₹320,000 in paise
            "useful_life_months": 60,
            "purchase_date": datetime(2024, 1, 1),
            "description": "Blenders, mixers, food processors, utensils",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "asset_id": "FA006",
            "asset_name": "Brand Logo & Setup",
            "category": "BRAND",
            "purchase_cost_inr": 4800000,  # ₹48,000 in paise
            "useful_life_months": 24,  # 2 years
            "purchase_date": datetime(2024, 1, 1),
            "description": "Brand identity, logo design, initial marketing materials",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]

    inserted_count = 0
    for asset in assets:
        try:
            existing = collection.find_one({"asset_id": asset["asset_id"]})
            if not existing:
                collection.insert_one(asset)
                inserted_count += 1
        except DuplicateKeyError:
            pass

    print(f"✓ Created {inserted_count} fixed assets ({len(assets) - inserted_count} already existed)")


def generate_sample_stock_movements(db):
    """Generate sample wastage/staff meal movements for past 4 months"""
    collection = db.stock_movement_log
    materials_collection = db.raw_material_inventory

    # Get all materials
    materials = list(materials_collection.find({}))
    if not materials:
        print("⚠ No raw materials found, skipping stock movements")
        return

    # Generate movements for past 4 months
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=120)  # ~4 months

    movements = []
    current_date = start_date

    # Generate wastage every 3-5 days
    while current_date <= end_date:
        # Pick 1-3 random perishable materials for wastage
        perishable_materials = [m for m in materials if m.get("is_perishable") == "Yes"]
        if perishable_materials:
            num_waste = random.randint(1, 3)
            for _ in range(num_waste):
                material = random.choice(perishable_materials)
                # Waste 2-5% of reorder level
                waste_qty = int(material.get("reorder_level", 100) * random.uniform(0.02, 0.05))

                movements.append({
                    "material_id": material["material_id"],
                    "material_name": material["material_name"],
                    "movement_type": "WASTE",
                    "quantity": -waste_qty,
                    "movement_date": current_date,
                    "movement_time": current_date.strftime("%H:%M:%S"),
                    "notes": "Expired/spoiled - routine wastage",
                    "created_by": "STF012",
                    "created_at": current_date
                })

        current_date += timedelta(days=random.randint(3, 5))

    # Generate staff meals - 1 per day
    current_date = start_date
    while current_date <= end_date:
        # Use some common ingredients for staff meals
        staff_meal_materials = [m for m in materials if m["material_id"] in ["RM001", "RM007", "RM012", "RM013"]]
        for material in staff_meal_materials[:2]:  # Use 2 ingredients per meal
            meal_qty = random.randint(50, 150)

            meal_time = current_date.replace(hour=14, minute=0, second=0)
            movements.append({
                "material_id": material["material_id"],
                "material_name": material["material_name"],
                "movement_type": "STAFF_MEAL",
                "quantity": -meal_qty,
                "movement_date": meal_time,
                "movement_time": meal_time.strftime("%H:%M:%S"),
                "notes": "Staff meal - lunch",
                "created_by": "SYSTEM",
                "created_at": meal_time
            })

        current_date += timedelta(days=1)

    # Insert movements
    inserted_count = 0
    for movement in movements:
        # Don't check for existing - just insert
        collection.insert_one(movement)
        inserted_count += 1

    print(f"✓ Created {inserted_count} stock movements for wastage/staff meals ({len(movements) - inserted_count} already existed)")


def main():
    """Main setup function"""
    restaurant_id = sys.argv[1] if len(sys.argv) > 1 else 'default'

    print("\n" + "="*60)
    print("P&L DATA SETUP")
    print("="*60)
    print(f"Restaurant ID: {restaurant_id}")
    print()

    client = get_mongodb_client()
    db = get_database(client)

    try:
        # 1. Create restaurant settings
        print("1. Creating restaurant settings...")
        create_restaurant_settings(db, restaurant_id)

        # 2. Create packaging materials
        print("\n2. Creating packaging materials...")
        create_packaging_materials(db)

        # 3. Create packaging BOM
        print("\n3. Creating packaging BOM...")
        create_packaging_bom(db)

        # 4. Create fixed assets
        print("\n4. Creating fixed assets...")
        create_fixed_assets(db)

        # 5. Generate stock movements
        print("\n5. Generating sample stock movements...")
        generate_sample_stock_movements(db)

        print("\n" + "="*60)
        print("✓ SETUP COMPLETE")
        print("="*60)
        print("\nYou can now generate detailed P&L reports!")
        print()

    except Exception as e:
        print(f"\n✗ Error during setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()

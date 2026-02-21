"""
Script to import raw material inventory data from Excel to MongoDB
"""
import asyncio
import sys
from pathlib import Path

import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_database, connect_to_database, close_database_connection
from datetime import datetime


async def import_inventory_data():
    """Import inventory data from Excel file"""
    # Try Docker path first, then local path
    docker_path = Path("/app/lexis_test_data/raw_material_inventory.xlsx")
    local_path = Path(__file__).parent.parent.parent / "lexis_test_data" / "raw_material_inventory.xlsx"

    excel_file = docker_path if docker_path.exists() else local_path

    if not excel_file.exists():
        print(f"Error: Excel file not found at {excel_file}")
        return

    print(f"Reading data from {excel_file}...")
    df = pd.read_excel(excel_file)

    print(f"Found {len(df)} records")

    # Connect to database
    await connect_to_database()
    db = get_database()
    collection = db.raw_material_inventory

    # Clear existing data
    print("Clearing existing inventory data...")
    await collection.delete_many({})

    # Prepare data for insertion
    items = []
    now = datetime.utcnow()

    for _, row in df.iterrows():
        item = {
            "material_id": str(row['Material_ID']),
            "material_name": str(row['Material_Name']),
            "category": str(row['Category']),
            "unit": str(row['Unit']),
            "unit_cost_inr": int(row['Unit_Cost_INR']),
            "reorder_level": int(row['Reorder_Level']),
            "reorder_qty": int(row['Reorder_Qty']),
            "current_stock": int(row['Current_Stock']),
            "max_stock": int(row['Max_Stock']),
            "lead_time_days": int(row['Lead_Time_Days']),
            "supplier_id": str(row['Supplier_ID']),
            "last_restock_date": str(row['Last_Restock_Date']) if pd.notna(row['Last_Restock_Date']) else None,
            "shelf_life_days": int(row['Shelf_Life_Days']),
            "storage_temp_c": str(row['Storage_Temp_C']),
            "is_perishable": str(row['Is_Perishable']),
            "created_at": now,
            "updated_at": now
        }
        items.append(item)

    # Insert data
    print(f"Inserting {len(items)} items into MongoDB...")
    result = await collection.insert_many(items)
    print(f"Successfully inserted {len(result.inserted_ids)} items")

    # Create indexes
    print("Creating indexes...")
    await collection.create_index("material_id", unique=True)
    await collection.create_index("category")
    await collection.create_index("is_perishable")

    print("Import completed successfully!")

    # Close database connection
    await close_database_connection()


if __name__ == "__main__":
    asyncio.run(import_inventory_data())

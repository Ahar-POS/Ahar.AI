"""
Export MongoDB data to CSVs in new_test_data/
Ensures Chatbot's DataLoader and other file-based tools see the new stable data.
"""

import pandas as pd
import pymongo
from pathlib import Path

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "ahar_pos"
OUTPUT_DIR = Path("backend/new_test_data")

def export_collection(db, collection_name, filename):
    print(f"Exporting {collection_name} to {filename}...")
    cursor = db[collection_name].find()
    data = list(cursor)
    if not data:
        print(f"  Warning: No data in {collection_name}")
        return
    
    df = pd.DataFrame(data)
    # Remove MongoDB internal _id
    if "_id" in df.columns:
        df.drop(columns=["_id"], inplace=True)
    
    # Save to CSV
    output_path = OUTPUT_DIR / filename
    df.to_csv(output_path, index=False)
    print(f"  Successfully exported {len(df)} rows.")

def main():
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Export core operational data
    export_collection(db, "orders", "orders.csv")
    export_collection(db, "raw_material_inventory", "raw_material_inventory.csv")
    export_collection(db, "stock_movement_log", "stock_movement_log.csv")
    export_collection(db, "menu_items", "menu_items.csv")
    
    print("\nExport complete. Chatbot DataLoader is now synced with MongoDB.")
    
    # Clear stale caches
    print("Clearing stale insights and forecasts...")
    db.agent_insights.delete_many({})
    db.demand_forecasts.delete_many({})
    print("Caches cleared. Agents will regenerate insights on next run.")
    
    client.close()

if __name__ == "__main__":
    main()

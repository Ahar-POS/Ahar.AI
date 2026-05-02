"""
Unified Stable Data Simulation Script - V2 (Recipe Based)

Generates consistent daily operations for Dec 1, 2025 – May 1, 2026.
Targets:
- Daily Revenue: ₹4L - ₹4.5L
- Daily COGS: ~16% (via actual Recipes)
- Avg Hyperpure Order: ~₹2.6L
- Avg Items/Order: ~4.3
- Reduces actual inventory in DB according to recipes.
"""

import random
import sys
from datetime import datetime, timedelta
import pymongo
from bson import ObjectId

# Configuration
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "ahar_pos"
RESTAURANT_ID = "antera_jubilee_hills"

# Financial Targets (in Paise)
DAILY_REV_MIN = 40000000  # ₹4 Lakhs
DAILY_REV_MAX = 45000000  # ₹4.5 Lakhs
HYPERPURE_TARGET = 26000000  # ₹2.6 Lakhs
WASTE_PERCENT = 0.04 # Approximate waste for movement generation

# Dates
START_DATE = datetime(2025, 12, 1)
END_DATE = datetime(2026, 5, 2)  # Extended to May 1 inclusive

# Popular items to weight probability
POPULAR_NAMES = [
    "Packaged Water Bottle (500 Ml)", "Coriander (kothimeera) Chicken", 
    "Apricot Trifle Delite", "Fresh Lime Soda", "Paya Shorba", 
    "Bhimavaram Royyala Vepudu", "Military Mutton Pulav", "Butter Naan", 
    "Thumsup", "Kodi Chips", "Guntur Karam Kodi Kebab", 
    "Chicken Dum Biryani (Regular)", "Chicken Boneless Biryani (Regular)", 
    "Anteras Spl Leches", "Chicken Kaju Pakoda", "Sitaphal Rabdi", 
    "Butter Garlic Naan", "Crispy Corn", "Pachimirchi Kodi Pulav", 
    "Anteras Spl Chicken Wings", "Ragi Sankati + Natu Kodi", "Curd Rice", 
    "Avakaya Pappu Annam Pachi Pulusu", "Chitti Muthyala Royyala Pulav", 
    "Mutton Dum Biryani (Regular)", "Phulka", "Nalgonda Mutton Fry B/L", 
    "Chicken Manchow Soup", "Gongura Paneer Pockets"
]

def main():
    rng = random.Random(42)
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]

    print("Fetching 230 menu items, 49 ingredients, and recipes...")
    menu_items = list(db.menu_items.find({"is_active": True}))
    ingredients_list = list(db.raw_material_inventory.find())
    recipe_list = list(db.recipe_bom.find())

    # Index for fast lookup
    recipes_map = {r["menu_item_id"]: r["ingredients"] for r in recipe_list}
    ingredients_map = {i["material_id"]: i for i in ingredients_list}
    
    # Virtual inventory tracking
    # Start with a realistic buffer: 12x reorder_level (approx 12 days of stock)
    virtual_inventory = {}
    baselines = {}
    for ing in ingredients_list:
        # Use reorder_level * 12 as the baseline
        mid = ing["material_id"]
        baseline = ing.get("reorder_level", 5000) * 12
        virtual_inventory[mid] = float(baseline)
        baselines[mid] = float(baseline)

    # Create weighting for menu items
    item_weights = []
    for item in menu_items:
        if item["name"] in POPULAR_NAMES:
            item_weights.append(10)
        else:
            item_weights.append(1)

    # Prepare for simulation
    current_date = START_DATE
    next_order_num = 1
    hyperpure_acc_usage_val = 0
    
    # Clear existing data for the range
    print(f"Clearing existing data from {START_DATE.date()} to {END_DATE.date()}...")
    db.orders.delete_many({"order_date": {"$gte": START_DATE, "$lt": END_DATE}})
    db.stock_movement_log.delete_many({"created_at": {"$gte": START_DATE, "$lt": END_DATE}})

    while current_date < END_DATE:
        day_str = current_date.strftime("%Y-%m-%d")
        target_rev = rng.randint(DAILY_REV_MIN, DAILY_REV_MAX)
        day_rev = 0
        day_orders = []
        
        # Track daily consumption for movements
        day_consumption = {} # material_id -> {qty, value}

        # 1. Generate Orders
        while day_rev < target_rev:
            num_items = rng.choices([1,2,3,4,5,6,7,8,9,10], weights=[10, 15, 20, 25, 15, 5, 4, 3, 2, 1])[0]
            chosen_items = rng.choices(menu_items, weights=item_weights, k=num_items)
            
            items_doc = []
            order_total = 0
            for itm in chosen_items:
                qty = rng.choices([1, 2], weights=[90, 10])[0]
                price = itm.get("price", 0)
                order_total += price * qty
                items_doc.append({
                    "menu_item_id": str(itm["_id"]),
                    "name_snapshot": itm["name"],
                    "price_snapshot": price,
                    "quantity": qty,
                    "status": "ready"
                    })
                # Update Consumption
                recipe_ingredients = recipes_map.get(str(itm["_id"]), [])
                for ri in recipe_ingredients:
                    mid = ri["material_id"]
                    used_qty = ri["quantity_per_serving"] * qty
                    
                    if mid not in day_consumption:
                        day_consumption[mid] = {"qty": 0.0, "val": 0}
                    
                    day_consumption[mid]["qty"] += used_qty
                    # Approximate value (paise) - using a stable average for simulation
                    # In real app this would call pricing_service
                    ing_meta = ingredients_map.get(mid, {})
                    unit_cost = ing_meta.get("unit_cost_inr", 100) # Fallback 1 INR/unit
                    day_consumption[mid]["val"] += int(used_qty * unit_cost)
                    
                    # Reduce virtual stock
                    virtual_inventory[mid] -= used_qty
            
            hour = rng.randint(12, 22)
            minute = rng.randint(0, 59)
            ts = current_date.replace(hour=hour, minute=minute)
            
            order = {
                "order_id": f"ORD{next_order_num:08d}",
                "order_number": next_order_num,
                "restaurant_id": RESTAURANT_ID,
                "total_amount": order_total,
                "order_date": current_date,
                "order_time": ts.strftime("%H:%M:%S"),
                "order_weekday": current_date.weekday(),
                "status": "completed",
                "items": items_doc,
                "created_at": ts
            }
            day_orders.append(order)
            day_rev += order_total
            next_order_num += 1

        if day_orders:
            db.orders.insert_many(day_orders)

        # 2. Generate Stock Movements (SALE & WASTE)
        sale_movements = []
        waste_movements = []
        day_total_usage_val = 0
        
        for mid, data in day_consumption.items():
            ing_meta = ingredients_map.get(mid, {})
            # SALE
            sale_movements.append({
                "movement_type": "SALE",
                "material_id": mid,
                "value_inr": data["val"],
                "quantity": data["qty"],
                "unit": ing_meta.get("unit", "Gram"),
                "created_at": current_date.replace(hour=23, minute=30),
                "restaurant_id": RESTAURANT_ID
            })
            
            # WASTE (approx 4% of usage)
            w_qty = data["qty"] * 0.05
            w_val = int(data["val"] * 0.05)
            waste_movements.append({
                "movement_type": "WASTE",
                "material_id": mid,
                "value_inr": w_val,
                "quantity": w_qty,
                "unit": ing_meta.get("unit", "Gram"),
                "created_at": current_date.replace(hour=23, minute=45),
                "restaurant_id": RESTAURANT_ID
            })
            
            # Reduce stock for waste too
            virtual_inventory[mid] -= w_qty
            day_total_usage_val += (data["val"] + w_val)
        
        if sale_movements:
            db.stock_movement_log.insert_many(sale_movements)
        if waste_movements:
            db.stock_movement_log.insert_many(waste_movements)

        # 3. Hyperpure Purchase Orders
        hyperpure_acc_usage_val += day_total_usage_val
        
        # Determine if we should refill
        # We refill if we've consumed enough OR if it's been 4 days
        # BUT: For the last 2 days (Apr 30, May 1), we DON'T refill 
        # so the Inventory Agent has something to do.
        if current_date < datetime(2026, 4, 30):
            if hyperpure_acc_usage_val >= HYPERPURE_TARGET:
                po_movements = []
                # Replenish exactly what was used to keep stock stable during the long history
                # We'll base it on current virtual inventory deficits
                for mid, current_v_qty in virtual_inventory.items():
                    target_v_qty = baselines.get(mid, 15000.0)
                    if current_v_qty < target_v_qty:
                        refill_qty = target_v_qty - current_v_qty
                        ing_meta = ingredients_map.get(mid, {})
                        val = int(refill_qty * ing_meta.get("unit_cost_inr", 100))
                        
                        po_movements.append({
                            "movement_type": "PURCHASE",
                            "material_id": mid,
                            "value_inr": val,
                            "quantity": refill_qty,
                            "unit": ing_meta.get("unit", "Gram"),
                            "created_at": current_date.replace(hour=10, minute=0),
                            "restaurant_id": RESTAURANT_ID,
                            "notes": "Hyperpure Bulk Order"
                        })
                        # Update virtual inventory
                        virtual_inventory[mid] += refill_qty
                
                if po_movements:
                    db.stock_movement_log.insert_many(po_movements)
                    print(f"  [{day_str}] Generated Hyperpure Refill")
                hyperpure_acc_usage_val = 0

        print(f"Processed {day_str} | Revenue: ₹{day_rev/100000:,.2f} Lakhs | Orders: {len(day_orders)}")
        current_date += timedelta(days=1)

    # 4. Sync final virtual inventory to DB
    print("\nSyncing final stock levels to raw_material_inventory...")
    for mid, qty in virtual_inventory.items():
        db.raw_material_inventory.update_one(
            {"material_id": mid},
            {"$set": {"current_stock": round(qty, 2)}}
        )

    print("\nSimulation Complete. Inventory is now depleted for May 1 testing.")
    client.close()

if __name__ == "__main__":
    main()

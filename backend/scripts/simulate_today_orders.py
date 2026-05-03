"""
Simulate Today's Operations

Generates orders for the current day up to the current time.
Deducts inventory immediately as orders are placed.
Prevents orders if they would cause any ingredient stock to drop below 0.
"""

import random
from datetime import datetime, time, timedelta
import pymongo

# Configuration
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "ahar_pos"
RESTAURANT_ID = "antera_jubilee_hills"

DAILY_REV_TARGET = 42500000  # ₹4.25 Lakhs full day target

POPULAR_NAMES = [
    "Packaged Water Bottle (500 Ml)", "Coriander (kothimeera) Chicken", 
    "Apricot Trifle Delite", "Fresh Lime Soda", "Paya Shorba", 
    "Bhimavaram Royyala Vepudu", "Military Mutton Pulav", "Butter Naan", 
    "Thumsup", "Kodi Chips", "Guntur Karam Kodi Kebab", 
    "Chicken Dum Biryani (Regular)", "Chicken Boneless Biryani (Regular)", 
    "Butter Garlic Naan", "Crispy Corn", "Pachimirchi Kodi Pulav", 
    "Anteras Spl Chicken Wings", "Ragi Sankati + Natu Kodi", "Curd Rice", 
    "Avakaya Pappu Annam Pachi Pulusu", "Chitti Muthyala Royyala Pulav", 
    "Mutton Dum Biryani (Regular)", "Phulka", "Nalgonda Mutton Fry B/L", 
    "Chicken Manchow Soup", "Gongura Paneer Pockets"
]

def main():
    rng = random.Random()
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]

    print("Loading menu, recipes, and current stock...")
    menu_items = list(db.menu_items.find({"is_active": True}))
    ingredients_list = list(db.raw_material_inventory.find())
    recipe_list = list(db.recipe_bom.find())

    recipes_map = {r["menu_item_id"]: r["ingredients"] for r in recipe_list}
    ingredients_map = {i["material_id"]: i for i in ingredients_list}
    
    # Live stock map to track levels during simulation
    current_stock_map = {i["material_id"]: float(i.get("current_stock", 0)) for i in ingredients_list}

    item_weights = [10 if item["name"] in POPULAR_NAMES else 1 for item in menu_items]

    import os
    target_time_str = os.getenv("SIM_TARGET_TIME")
    if target_time_str:
        now = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M")
    else:
        now = datetime.now()
    
    today_start = datetime.combine(now.date(), time(10, 0)) # Assuming 10 AM open

    if now < today_start:
        print("Restaurant hasn't opened yet (Opens at 10 AM). Nothing to simulate.")
        return

    # Calculate proportional revenue target based on elapsed time (13-hour operational window)
    operating_hours = 13
    elapsed_hours = (now - today_start).total_seconds() / 3600
    if elapsed_hours > operating_hours:
        elapsed_hours = operating_hours
    
    target_rev = int(DAILY_REV_TARGET * (elapsed_hours / operating_hours))
    print(f"Time is {now.strftime('%I:%M %p')}. Simulating up to ₹{target_rev/10000000:,.2f} Lakhs target.")

    # Get the latest order number to continue incrementing
    last_order = db.orders.find_one(sort=[("order_number", pymongo.DESCENDING)])
    next_order_num = (last_order["order_number"] + 1) if last_order and "order_number" in last_order else 1

    current_sim_time = today_start
    day_rev = 0
    orders_placed = 0
    orders_skipped = 0

    while day_rev < target_rev and current_sim_time <= now:
        # ... (rest of the loop) ...
        num_items = rng.choices([1,2,3,4,5,6], weights=[20, 30, 20, 15, 10, 5])[0]
        chosen_items = rng.choices(menu_items, weights=item_weights, k=num_items)
        
        required_ingredients = {}
        order_total = 0
        items_doc = []

        # Build order details and calculate required ingredients
        for itm in chosen_items:
            qty = rng.choices([1, 2], weights=[85, 15])[0]
            price = itm.get("price", 0)
            order_total += price * qty
            
            items_doc.append({
                "menu_item_id": str(itm["_id"]),
                "name_snapshot": itm["name"],
                "price_snapshot": price,
                "quantity": qty,
                "status": "ready"
            })
            
            recipe_ingredients = recipes_map.get(str(itm["_id"]), [])
            for ri in recipe_ingredients:
                mid = ri["material_id"]
                used_qty = ri["quantity_per_serving"] * qty
                required_ingredients[mid] = required_ingredients.get(mid, 0) + used_qty

        # 1. Check if ANY ingredient would go below 0
        can_fulfill = True
        for mid, req_qty in required_ingredients.items():
            if current_stock_map.get(mid, 0) < req_qty:
                can_fulfill = False
                break
        
        if not can_fulfill:
            orders_skipped += 1
            # Advance time slightly to prevent infinite looping if stock is depleted
            current_sim_time += timedelta(minutes=rng.randint(1, 5))
            continue

        # 2. Fulfill Order: Deduct stock and log movements
        sale_movements = []
        waste_movements = []
        
        for mid, req_qty in required_ingredients.items():
            # Deduct from live map
            current_stock_map[mid] -= req_qty
            
            # DB Update immediately to stay in sync
            db.raw_material_inventory.update_one(
                {"material_id": mid},
                {"$inc": {"current_stock": -req_qty}}
            )

            ing_meta = ingredients_map.get(mid, {})
            unit_cost = ing_meta.get("unit_cost_inr", 100)
            val = int(req_qty * unit_cost)

            # SALE Movement
            sale_movements.append({
                "movement_type": "SALE",
                "material_id": mid,
                "value_inr": val,
                "quantity": req_qty,
                "unit": ing_meta.get("unit", "Gram"),
                "created_at": current_sim_time,
                "restaurant_id": RESTAURANT_ID
            })

            # Simulate immediate WASTE (5%)
            w_qty = req_qty * 0.05
            if current_stock_map.get(mid, 0) >= w_qty:
                w_val = int(val * 0.05)
                current_stock_map[mid] -= w_qty
                db.raw_material_inventory.update_one(
                    {"material_id": mid},
                    {"$inc": {"current_stock": -w_qty}}
                )
                waste_movements.append({
                    "movement_type": "WASTE",
                    "material_id": mid,
                    "value_inr": w_val,
                    "quantity": w_qty,
                    "unit": ing_meta.get("unit", "Gram"),
                    "created_at": current_sim_time + timedelta(seconds=10),
                    "restaurant_id": RESTAURANT_ID
                })

        if sale_movements:
            db.stock_movement_log.insert_many(sale_movements)
        if waste_movements:
            db.stock_movement_log.insert_many(waste_movements)

        # 3. Create the Order document
        channel = rng.choices(
            ["dine_in", "zomato", "swiggy", "walk_in"],
            weights=[50, 25, 15, 10]
        )[0]
        kitchen_start = current_sim_time + timedelta(minutes=rng.randint(2, 5))
        kitchen_end = kitchen_start + timedelta(minutes=rng.randint(10, 25))
        order = {
            "order_id": f"ORD{next_order_num:08d}",
            "order_number": next_order_num,
            "restaurant_id": RESTAURANT_ID,
            "total_amount": order_total,
            "order_date": current_sim_time,
            "order_time": current_sim_time.strftime("%H:%M:%S"),
            "order_hour": current_sim_time.hour,
            "order_weekday": current_sim_time.weekday(),
            "order_channel": channel,
            "order_type": "dine_in" if channel == "dine_in" else "takeaway",
            "status": "completed",
            "sent_to_kitchen_at": kitchen_start,
            "completed_at": kitchen_end,
            "items": items_doc,
            "created_at": current_sim_time
        }
        db.orders.insert_one(order)
        
        day_rev += order_total
        next_order_num += 1
        orders_placed += 1

        # Advance time by a few minutes for the next order
        current_sim_time += timedelta(minutes=rng.randint(2, 10))

    print(f"\nFinished simulation for today!")
    print(f"Orders Placed: {orders_placed}")
    print(f"Orders Skipped (Insufficient Stock): {orders_skipped}")
    print(f"Revenue Generated: ₹{day_rev/10000000:,.2f} Lakhs")

    client.close()

if __name__ == "__main__":
    main()

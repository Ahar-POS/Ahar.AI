"""
Seed script: generate orders + stock movements for Jan 1 – Apr 11, 2026.

Bases patterns on actual Dec 2025 data:
  - Hourly distribution from Dec orders
  - Per-weekday daily volume
  - Item mix from top 30 most-ordered menu items
  - ±15% daily random variation

Also generates stock_movement_log (SALE at 30% of revenue, WASTE at 4%)
so the P&L and food-cost panels show real numbers.

Run from the backend/ directory (or project root):
  python3 backend/seed_jan_apr_2026.py
"""

import random
import sys
from datetime import datetime, timedelta

import pymongo

MONGO_URI = "mongodb://localhost:27017"
DB_NAME   = "ahar_pos"

RESTAURANT_ID = "antera_jubilee_hills"

# ── Hourly weights extracted from Dec 2025 ─────────────────────────────────
# Keys are hours present in Dec data; missing hours get weight 0
HOUR_WEIGHTS_RAW = {
    0: 139, 1: 8, 11: 2,
    12: 813, 13: 1237, 14: 1527, 15: 1410,
    16: 950, 17: 485, 18: 576,
    19: 1131, 20: 1483, 21: 1658, 22: 1536, 23: 931,
}
# Build ordered list for random.choices
HOURS   = list(HOUR_WEIGHTS_RAW.keys())
H_WGTS  = [HOUR_WEIGHTS_RAW[h] for h in HOURS]

# ── Daily base volumes per weekday (0=Mon … 6=Sun) from Dec 2025 avg ───────
# Mon:1591/5 Tue:1663/5 Wed:2440/5 Thu:1816/4 Fri:1952/4 Sat:2043/4 Sun:2382/4
DAY_BASE = {0: 318, 1: 333, 2: 488, 3: 454, 4: 488, 5: 511, 6: 596}

# ── Top menu items (id, name_snapshot, price_snapshot) ────────────────────
MENU_ITEMS = [
    ("69dabdbc90d7b2174cca1fce", "Packaged Water Bottle (500 Ml)", 3000),
    ("69dabdbc90d7b2174cca1ef7", "Coriander (kothimeera) Chicken",  49500),
    ("69dabdbc90d7b2174cca1eaa", "Apricot Trifle Delite",           22500),
    ("69dabdbc90d7b2174cca1ef6", "Coriander (Kothimeera) Chicken",  54500),
    ("69dabdbc90d7b2174cca1f11", "Fresh Lime Soda",                 14500),
    ("69dabdbc90d7b2174cca1fd3", "Paya Shorba",                     27500),
    ("69dabdbc90d7b2174cca1eba", "Bhimavaram Royyala Vepudu",       57500),
    ("69dabdbc90d7b2174cca1f8a", "Military Mutton Pulav",           59500),
    ("69dabdbc90d7b2174cca1ecd", "Butter Naan",                      9000),
    ("69dabdbc90d7b2174cca2026", "Thumsup",                          9000),
    ("69dabdbc90d7b2174cca1f73", "Kodi Chips",                      47500),
    ("69dabdbc90d7b2174cca1f42", "Guntur Karam Kodi Kebab",         49500),
    ("69dabdbc90d7b2174cca1ed9", "Chicken Dum Biryani (Regular)",   42500),
    ("69dabdbc90d7b2174cca1ed4", "Chicken Boneless Biryani (Regular)", 44500),
    ("69dabdbc90d7b2174cca1ea8", "Anteras Spl Leches",              19500),
    ("69dabdbc90d7b2174cca1edd", "Chicken Kaju Pakoda",             49500),
    ("69dabdbc90d7b2174cca1ff9", "Sitaphal Rabdi",                  22500),
    ("69dabdbc90d7b2174cca1ecb", "Butter Garlic Naan",              10000),
    ("69dabdbc90d7b2174cca1eff", "Crispy Corn",                     37500),
    ("69dabdbc90d7b2174cca1fc6", "Pachimirchi Kodi Pulav",          47500),
    ("69dabdbc90d7b2174cca1ea7", "Anteras Spl Chicken Wings",       49500),
    ("69dabdbc90d7b2174cca1fe8", "Ragi Sankati + Natu Kodi",        52500),
    ("69dabdbc90d7b2174cca1f01", "Curd Rice",                       27500),
    ("69dabdbc90d7b2174cca1ead", "Avakaya Pappu Annam Pachi Pulusu", 37500),
    ("69dabdbc90d7b2174cca1eeb", "Chitti Muthyala Royyala Pulav",   54500),
    ("69dabdbc90d7b2174cca1f9a", "Mutton Dum Biryani (Regular)",    54500),
    ("69dabdbc90d7b2174cca1fd8", "Phulka",                           8000),
    ("69dabdbc90d7b2174cca1fa3", "Nalgonda Mutton Fry B/L",         64500),
    ("69dabdbc90d7b2174cca1ee0", "Chicken Manchow Soup",            22500),
    ("69dabdbc90d7b2174cca1f33", "Gongura Paneer Pockets",          44500),
]
ITEM_IDS   = [m[0] for m in MENU_ITEMS]
# Popularity weights (mirror their Dec order frequency)
ITEM_WGTS  = [
    11737, 5218, 4212, 3637, 3302, 3000, 2981, 2845,
    2791,  2759, 2628, 2567, 2523, 2394, 2184, 2145,
    2108,  2054, 1994, 1982, 1910, 1877, 1825, 1779,
    1776,  1775, 1768, 1669, 1669, 1669,
]

# ── Item count distribution (1-25 items, weighted by Dec distribution) ─────
# P(n items) computed from Dec counts — tail is small so cap at 25
ITEM_COUNT_WEIGHTS = [
    472, 284, 232, 306, 404, 405, 512, 613, 757, 746,
    761, 912, 852, 793, 730, 691, 639, 566, 478, 443,
    369, 312, 284, 220, 190,
]
ITEM_COUNTS = list(range(1, 26))

PAYMENT_TYPES = ["Online (Swiggy)", "Online (Zomato)", "Cash", "Card", "UPI"]
PAY_WGTS      = [30, 25, 15, 15, 15]
ORDER_TYPES   = ["ONLINE", "DINE_IN", "TAKEAWAY"]
ORDER_WGTS    = [55, 35, 10]


def make_order(order_number: int, order_date: datetime, rng: random.Random) -> dict:
    hour     = rng.choices(HOURS, weights=H_WGTS)[0]
    minute   = rng.randint(0, 59)
    second   = rng.randint(0, 59)
    ts       = order_date.replace(hour=hour, minute=minute, second=second)

    n_items  = rng.choices(ITEM_COUNTS, weights=ITEM_COUNT_WEIGHTS)[0]
    chosen   = rng.choices(MENU_ITEMS, weights=ITEM_WGTS, k=n_items)

    items_doc = []
    total     = 0
    for mid, name, price in chosen:
        qty   = rng.choices([1, 2, 3], weights=[70, 20, 10])[0]
        total += price * qty
        items_doc.append({
            "menu_item_id":   mid,
            "name_snapshot":  name,
            "price_snapshot": price,
            "quantity":       qty,
            "addon_name":     "",
            "addon_price":    0,
            "status":         "READY",
        })

    otype   = rng.choices(ORDER_TYPES, weights=ORDER_WGTS)[0]
    pay     = rng.choices(PAYMENT_TYPES, weights=PAY_WGTS)[0]
    area    = "Swiggy" if "Swiggy" in pay else ("Zomato" if "Zomato" in pay else "Dine-In")

    return {
        "order_id":          f"ORD{order_number:08d}",
        "order_number":      order_number,
        "restaurant_id":     RESTAURANT_ID,
        "order_type":        otype,
        "table_id":          None,
        "status":            "COMPLETED",
        "total_amount":      total,
        "staff_id":          "Autoaccept",
        "payment_type":      pay,
        "area":              area,
        "order_date":        order_date,
        "order_time":        ts.strftime("%H:%M:%S"),
        "order_hour":        hour,
        "order_weekday":     order_date.weekday(),
        "is_weekend":        order_date.weekday() >= 5,
        "is_holiday":        False,
        "holiday_name":      None,
        "created_at":        ts,
        "completed_at":      ts,
        "sent_to_kitchen_at": ts,
        "items":             items_doc,
    }


def make_movement(day: datetime, movement_type: str, value_paise: int) -> dict:
    mat = random.choice(["RM001", "RM002", "RM003", "RM004", "RM005"])
    return {
        "movement_type": movement_type,
        "material_id":   mat,
        "value_inr":     value_paise,        # field name matches dashboard service query
        "quantity":      round(value_paise / 4500),
        "unit":          "g",
        "created_at":    day.replace(hour=23, minute=0, second=0),
        "restaurant_id": RESTAURANT_ID,
        "notes":         f"Auto-seed {movement_type}",
    }


def main():
    rng = random.Random(42)  # reproducible

    client = pymongo.MongoClient(MONGO_URI)
    db     = client[DB_NAME]

    start_date = datetime(2026, 1, 1)
    end_date   = datetime(2026, 4, 12)   # exclusive (up to and including Apr 11)

    # Find the last order_number in DB to continue from
    last = db.orders.find_one(sort=[("order_number", -1)])
    next_order_num = (last["order_number"] + 1) if last else 1
    print(f"Starting at order_number {next_order_num}")

    days = []
    d = start_date
    while d < end_date:
        days.append(d)
        d += timedelta(days=1)

    print(f"Generating orders for {len(days)} days ({start_date.date()} → {(end_date - timedelta(1)).date()})")

    total_orders_inserted = 0
    total_movements_inserted = 0
    BATCH = 500

    order_buf    = []
    movement_buf = []

    for day in days:
        base   = DAY_BASE[day.weekday()]
        variation = rng.uniform(0.85, 1.15)
        count  = max(50, int(base * variation))

        day_revenue_paise = 0
        for _ in range(count):
            order = make_order(next_order_num, day, rng)
            day_revenue_paise += order["total_amount"]
            order_buf.append(order)
            next_order_num += 1

        # SALE movement = ~30% of revenue (food cost)
        cogs  = int(day_revenue_paise * 0.30 * rng.uniform(0.90, 1.10))
        movement_buf.append(make_movement(day, "SALE", cogs))

        # WASTE movement = ~4% of revenue
        waste = int(day_revenue_paise * 0.04 * rng.uniform(0.80, 1.20))
        movement_buf.append(make_movement(day, "WASTE", waste))

        if len(order_buf) >= BATCH:
            db.orders.insert_many(order_buf, ordered=False)
            total_orders_inserted += len(order_buf)
            order_buf = []
            print(f"  {day.date()}  {total_orders_inserted} orders so far…", end="\r")
            sys.stdout.flush()

        if len(movement_buf) >= 100:
            db.stock_movement_log.insert_many(movement_buf, ordered=False)
            total_movements_inserted += len(movement_buf)
            movement_buf = []

    # Flush remaining
    if order_buf:
        db.orders.insert_many(order_buf, ordered=False)
        total_orders_inserted += len(order_buf)
    if movement_buf:
        db.stock_movement_log.insert_many(movement_buf, ordered=False)
        total_movements_inserted += len(movement_buf)

    print(f"\nDone. Inserted {total_orders_inserted} orders and {total_movements_inserted} stock movements.")
    client.close()


if __name__ == "__main__":
    main()

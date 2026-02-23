#!/usr/bin/env python3
"""
Generate full-scale restaurant test data as CSV files.

Output files:
- menu_items.csv
- recipe_bom.csv
- raw_material_inventory.csv
- orders.csv
- order_line_items.csv
- stock_movement_log.csv
- supplier_master.csv
"""

from __future__ import annotations

import csv
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


RNG = random.Random(20260223)
OUTPUT_DIR = Path(__file__).resolve().parent

START_DATE = date(2025, 10, 21)
END_DATE = date(2026, 1, 28)
MIN_ORDERS = 6000
MAX_ORDERS = 8000
TARGET_CONSUMPTION_MOVES = 520
TARGET_RESTOCK_MOVES = 130
TARGET_WASTE_MOVES = 35
TARGET_ADJUSTMENT_MOVES = 15


def bool_str(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def daterange(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def random_date(start: date, end: date) -> date:
    return start + timedelta(days=RNG.randint(0, (end - start).days))


def random_time_str(start_hour: int, end_hour: int) -> str:
    hour = RNG.randint(start_hour, end_hour)
    minute = RNG.randint(0, 59)
    second = RNG.randint(0, 59)
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def choose_weighted(items: Sequence[str], weights: Sequence[float]) -> str:
    return RNG.choices(items, weights=weights, k=1)[0]


def choose_weighted_unique(items: Sequence[str], weights: Sequence[float], k: int) -> List[str]:
    available_items = list(items)
    available_weights = list(weights)
    selected: List[str] = []

    picks = min(k, len(available_items))
    for _ in range(picks):
        chosen = RNG.choices(available_items, weights=available_weights, k=1)[0]
        idx = available_items.index(chosen)
        selected.append(chosen)
        available_items.pop(idx)
        available_weights.pop(idx)

    return selected


@dataclass(frozen=True)
class MaterialSeed:
    name: str
    category: str
    unit: str
    unit_cost_inr: int
    is_perishable: bool


@dataclass(frozen=True)
class MenuSeed:
    menu_item_id: str
    name: str
    category: str
    price_inr: int
    description: str
    prep_type: str
    tags: str
    is_available: bool
    popularity_score: int
    created_at: str


SUPPLIERS = [
    {
        "supplier_id": "SUP001",
        "supplier_name": "Fresh Meats Co",
        "contact_person": "Rajesh Kumar",
        "phone": "+91-9876543210",
        "email": "rajesh@freshmeats.com",
        "address": "123 MG Road",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560001",
        "payment_terms": "NET_30",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
    {
        "supplier_id": "SUP002",
        "supplier_name": "Coastal Catch Foods",
        "contact_person": "Neha Menon",
        "phone": "+91-9876543211",
        "email": "neha@coastalcatch.com",
        "address": "44 Indiranagar 100ft Road",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560038",
        "payment_terms": "NET_21",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
    {
        "supplier_id": "SUP003",
        "supplier_name": "Veggie Fresh",
        "contact_person": "Amit Patel",
        "phone": "+91-9876543212",
        "email": "amit@veggiefresh.com",
        "address": "78 HAL Main Road",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560008",
        "payment_terms": "NET_15",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
    {
        "supplier_id": "SUP004",
        "supplier_name": "FarmToFork Greens",
        "contact_person": "Sowmya Reddy",
        "phone": "+91-9876543213",
        "email": "sowmya@farmtofork.in",
        "address": "12 Whitefield Main Road",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560066",
        "payment_terms": "NET_15",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
    {
        "supplier_id": "SUP005",
        "supplier_name": "Dairy Best",
        "contact_person": "Priya Sharma",
        "phone": "+91-9876543214",
        "email": "priya@dairybest.com",
        "address": "19 Dairy Circle",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560029",
        "payment_terms": "NET_20",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
    {
        "supplier_id": "SUP006",
        "supplier_name": "Morning Milk Pvt Ltd",
        "contact_person": "Kiran Dev",
        "phone": "+91-9876543215",
        "email": "kiran@morningmilk.in",
        "address": "4 Bannerghatta Road",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560076",
        "payment_terms": "CASH",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
    {
        "supplier_id": "SUP007",
        "supplier_name": "Daily Bakery",
        "contact_person": "Pooja Nair",
        "phone": "+91-9876543216",
        "email": "pooja@dailybakery.com",
        "address": "45 Brigade Road",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560025",
        "payment_terms": "NET_10",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
    {
        "supplier_id": "SUP008",
        "supplier_name": "Grain Basket Supplies",
        "contact_person": "Arjun Shetty",
        "phone": "+91-9876543217",
        "email": "arjun@grainbasket.in",
        "address": "6 Mysore Road",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560026",
        "payment_terms": "NET_30",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
    {
        "supplier_id": "SUP009",
        "supplier_name": "Spice World",
        "contact_person": "Sunita Reddy",
        "phone": "+91-9876543218",
        "email": "sunita@spiceworld.com",
        "address": "90 Koramangala",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560034",
        "payment_terms": "NET_30",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
    {
        "supplier_id": "SUP010",
        "supplier_name": "Dry Goods Hub",
        "contact_person": "Farhan Ali",
        "phone": "+91-9876543219",
        "email": "farhan@drygoodshub.in",
        "address": "31 Commercial Street",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560001",
        "payment_terms": "NET_21",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
    {
        "supplier_id": "SUP011",
        "supplier_name": "Beverage Source",
        "contact_person": "Ananya Rao",
        "phone": "+91-9876543220",
        "email": "ananya@beveragesource.in",
        "address": "14 Residency Road",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560025",
        "payment_terms": "NET_30",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
    {
        "supplier_id": "SUP012",
        "supplier_name": "Oil & Essentials Traders",
        "contact_person": "Vikram Joshi",
        "phone": "+91-9876543221",
        "email": "vikram@oilessentials.in",
        "address": "22 Yelahanka Main Road",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560064",
        "payment_terms": "NET_15",
        "is_active": "TRUE",
        "created_at": "2024-01-10",
    },
]


MATERIALS = [
    MaterialSeed("Chicken Breast", "Proteins", "Gram", 60, True),
    MaterialSeed("Fish Fillet", "Proteins", "Gram", 90, True),
    MaterialSeed("Paneer", "Proteins", "Gram", 45, True),
    MaterialSeed("Egg", "Proteins", "Piece", 700, True),
    MaterialSeed("Burger Bun", "Bakery", "Piece", 900, True),
    MaterialSeed("Wrap Tortilla", "Bakery", "Piece", 1100, True),
    MaterialSeed("Sandwich Bread", "Bakery", "Piece", 250, True),
    MaterialSeed("Noodles", "Bakery", "Gram", 18, False),
    MaterialSeed("Basmati Rice", "Bakery", "Gram", 14, False),
    MaterialSeed("Dosa Batter", "Bakery", "Gram", 12, True),
    MaterialSeed("Potato", "Vegetables", "Gram", 7, False),
    MaterialSeed("Lettuce", "Vegetables", "Gram", 12, True),
    MaterialSeed("Tomato", "Vegetables", "Gram", 10, True),
    MaterialSeed("Onion", "Vegetables", "Gram", 8, True),
    MaterialSeed("Capsicum", "Vegetables", "Gram", 16, True),
    MaterialSeed("Cabbage", "Vegetables", "Gram", 7, True),
    MaterialSeed("Carrot", "Vegetables", "Gram", 9, True),
    MaterialSeed("Cucumber", "Vegetables", "Gram", 8, True),
    MaterialSeed("Coriander", "Vegetables", "Gram", 20, True),
    MaterialSeed("Green Chili", "Vegetables", "Gram", 18, True),
    MaterialSeed("Lemon", "Vegetables", "Piece", 500, True),
    MaterialSeed("Garlic", "Vegetables", "Gram", 15, True),
    MaterialSeed("Ginger", "Vegetables", "Gram", 17, True),
    MaterialSeed("Cheese Slice", "Dairy", "Piece", 1800, True),
    MaterialSeed("Butter", "Dairy", "Gram", 25, True),
    MaterialSeed("Milk", "Dairy", "ML", 7, True),
    MaterialSeed("Yogurt", "Dairy", "Gram", 11, True),
    MaterialSeed("Cream", "Dairy", "Gram", 20, True),
    MaterialSeed("Mayonnaise", "Dairy", "Gram", 14, False),
    MaterialSeed("Cooking Oil", "Oils", "ML", 6, False),
    MaterialSeed("Salt", "Spices", "Gram", 1, False),
    MaterialSeed("Black Pepper", "Spices", "Gram", 45, False),
    MaterialSeed("Chili Powder", "Spices", "Gram", 30, False),
    MaterialSeed("Garam Masala", "Spices", "Gram", 38, False),
    MaterialSeed("Turmeric Powder", "Spices", "Gram", 22, False),
    MaterialSeed("Chaat Masala", "Spices", "Gram", 34, False),
    MaterialSeed("Sugar", "Spices", "Gram", 4, False),
    MaterialSeed("Mango Pulp", "Beverages", "Gram", 15, True),
    MaterialSeed("Coffee Powder", "Beverages", "Gram", 70, False),
    MaterialSeed("Gulab Jamun Mix", "Bakery", "Gram", 28, False),
]


MENU_ITEMS = [
    MenuSeed(
        "MENU001",
        "Smoky Chicken Burger",
        "Main Course",
        24500,
        "Grilled chicken burger with lettuce, tomato and signature mayo.",
        "GRILL",
        "CHICKEN,DAIRY,VEGETABLES",
        True,
        9,
        "2024-01-15",
    ),
    MenuSeed(
        "MENU002",
        "Paneer Tikka Wrap",
        "Main Course",
        21500,
        "Char-grilled paneer wrap with onions and capsicum.",
        "GRILL",
        "VEGETABLES,DAIRY,SPICY",
        True,
        7,
        "2024-01-15",
    ),
    MenuSeed(
        "MENU003",
        "Veggie Club Sandwich",
        "Main Course",
        16500,
        "Triple layer sandwich with fresh vegetables and cheese.",
        "RAW",
        "VEGETABLES,DAIRY,VEGAN",
        True,
        6,
        "2024-01-20",
    ),
    MenuSeed(
        "MENU004",
        "Chicken Rice Bowl",
        "Main Course",
        22900,
        "Spiced chicken served over steamed basmati rice.",
        "GRILL",
        "CHICKEN,SPICY,VEGETABLES",
        True,
        7,
        "2024-02-01",
    ),
    MenuSeed(
        "MENU005",
        "Masala Dosa",
        "Main Course",
        13500,
        "Crisp dosa filled with masala potato and served hot.",
        "FRY",
        "VEGETABLES,SPICY,VEGAN",
        True,
        10,
        "2024-01-18",
    ),
    MenuSeed(
        "MENU006",
        "Grilled Fish Wrap",
        "Main Course",
        26800,
        "Lemon chili fish wrapped in soft tortilla.",
        "GRILL",
        "FISH,SPICY,VEGETABLES",
        True,
        6,
        "2024-02-10",
    ),
    MenuSeed(
        "MENU007",
        "Veg Hakka Noodles",
        "Main Course",
        17900,
        "Wok tossed noodles with mixed vegetables.",
        "FRY",
        "VEGETABLES,SPICY,PASTA",
        True,
        6,
        "2024-02-05",
    ),
    MenuSeed(
        "MENU008",
        "Egg Bhurji Roll",
        "Main Course",
        14500,
        "Spiced scrambled egg roll with onions and tomato.",
        "FRY",
        "VEGETABLES,SPICY",
        True,
        5,
        "2024-03-01",
    ),
    MenuSeed(
        "MENU009",
        "Paneer Butter Rice",
        "Main Course",
        23800,
        "Rich paneer butter masala paired with basmati rice.",
        "GRILL",
        "VEGETABLES,DAIRY,SPICY",
        True,
        5,
        "2024-03-10",
    ),
    MenuSeed(
        "MENU010",
        "French Fries",
        "Starters",
        8900,
        "Classic crispy potato fries with seasoning.",
        "FRY",
        "VEGETABLES,VEGAN",
        True,
        8,
        "2024-01-15",
    ),
    MenuSeed(
        "MENU011",
        "Chili Potato",
        "Starters",
        11200,
        "Spicy tossed potato fingers with onion and capsicum.",
        "FRY",
        "VEGETABLES,SPICY,VEGAN",
        True,
        5,
        "2024-02-11",
    ),
    MenuSeed(
        "MENU012",
        "Crispy Chicken Bites",
        "Starters",
        14200,
        "Juicy chicken bites tossed with house masala.",
        "FRY",
        "CHICKEN,SPICY",
        True,
        4,
        "2024-02-14",
    ),
    MenuSeed(
        "MENU013",
        "Garlic Bread Sticks",
        "Starters",
        9600,
        "Garlic butter bread sticks finished with cheese.",
        "GRILL",
        "DAIRY,VEGETABLES",
        True,
        3,
        "2024-03-02",
    ),
    MenuSeed(
        "MENU014",
        "Mango Lassi",
        "Beverages",
        7600,
        "Creamy mango yogurt drink.",
        "BEVERAGE",
        "DAIRY,VEGETABLES",
        True,
        9,
        "2024-01-20",
    ),
    MenuSeed(
        "MENU015",
        "Masala Lemonade",
        "Beverages",
        6400,
        "Refreshing lemon cooler with Indian spices.",
        "BEVERAGE",
        "SPICY,VEGAN,VEGETABLES",
        True,
        7,
        "2024-03-05",
    ),
    MenuSeed(
        "MENU016",
        "Cold Coffee",
        "Beverages",
        9200,
        "Iced coffee blended with milk and cream.",
        "BEVERAGE",
        "DAIRY,VEGETABLES",
        True,
        5,
        "2024-02-20",
    ),
    MenuSeed(
        "MENU017",
        "Spiced Buttermilk",
        "Beverages",
        5800,
        "Light buttermilk with herbs and pepper.",
        "BEVERAGE",
        "DAIRY,SPICY,VEGETABLES",
        True,
        2,
        "2024-03-12",
    ),
    MenuSeed(
        "MENU018",
        "Gulab Jamun",
        "Desserts",
        9900,
        "Warm gulab jamun served in sugar syrup.",
        "DESSERT",
        "DAIRY,VEGETABLES",
        True,
        4,
        "2024-02-25",
    ),
    MenuSeed(
        "MENU019",
        "Bread Butter Pudding",
        "Desserts",
        12400,
        "Baked bread pudding with cream and butter.",
        "DESSERT",
        "DAIRY,VEGETABLES",
        False,
        1,
        "2024-03-14",
    ),
    MenuSeed(
        "MENU020",
        "Mango Yogurt Cup",
        "Desserts",
        10900,
        "Chilled mango and yogurt dessert cup.",
        "DESSERT",
        "DAIRY,VEGETABLES",
        True,
        2,
        "2024-03-16",
    ),
]


RECIPES = {
    "MENU001": [("RM001", 140, True), ("RM005", 1, True), ("RM012", 20, False), ("RM013", 25, False), ("RM024", 1, False), ("RM029", 18, False), ("RM031", 2, False)],
    "MENU002": [("RM003", 120, True), ("RM006", 1, True), ("RM015", 30, False), ("RM014", 25, False), ("RM027", 30, False), ("RM034", 3, True), ("RM030", 12, False)],
    "MENU003": [("RM007", 3, True), ("RM012", 15, False), ("RM013", 20, False), ("RM018", 20, False), ("RM024", 1, True), ("RM029", 15, False)],
    "MENU004": [("RM001", 130, True), ("RM009", 120, True), ("RM014", 25, False), ("RM015", 25, False), ("RM023", 6, False), ("RM030", 10, False), ("RM034", 2, False)],
    "MENU005": [("RM010", 220, True), ("RM011", 90, True), ("RM014", 20, False), ("RM020", 4, False), ("RM025", 12, False), ("RM031", 2, False), ("RM030", 8, False)],
    "MENU006": [("RM002", 130, True), ("RM006", 1, True), ("RM012", 15, False), ("RM013", 20, False), ("RM021", 1, False), ("RM033", 2, False), ("RM030", 10, False)],
    "MENU007": [("RM008", 160, True), ("RM015", 20, False), ("RM016", 25, False), ("RM017", 20, False), ("RM022", 5, False), ("RM030", 12, False), ("RM032", 2, False), ("RM031", 2, False)],
    "MENU008": [("RM004", 2, True), ("RM006", 1, True), ("RM014", 20, False), ("RM013", 20, False), ("RM033", 2, False), ("RM025", 10, False), ("RM031", 2, False)],
    "MENU009": [("RM003", 110, True), ("RM009", 130, True), ("RM025", 15, False), ("RM028", 20, False), ("RM014", 20, False), ("RM034", 2, False), ("RM031", 2, False)],
    "MENU010": [("RM011", 180, True), ("RM030", 35, True), ("RM031", 3, False), ("RM036", 2, False)],
    "MENU011": [("RM011", 170, True), ("RM030", 28, True), ("RM033", 3, False), ("RM014", 20, False), ("RM015", 20, False), ("RM036", 2, False)],
    "MENU012": [("RM001", 120, True), ("RM030", 25, True), ("RM034", 2, False), ("RM033", 2, False), ("RM031", 2, False), ("RM027", 20, False)],
    "MENU013": [("RM007", 4, True), ("RM025", 18, True), ("RM022", 6, False), ("RM024", 1, False), ("RM032", 1, False)],
    "MENU014": [("RM038", 120, True), ("RM027", 150, True), ("RM037", 15, False), ("RM026", 60, False)],
    "MENU015": [("RM021", 1, True), ("RM037", 18, False), ("RM032", 1, False), ("RM031", 1, False), ("RM023", 4, False), ("RM036", 1, False)],
    "MENU016": [("RM039", 8, True), ("RM026", 180, True), ("RM037", 20, False), ("RM028", 15, False)],
    "MENU017": [("RM027", 120, True), ("RM026", 80, False), ("RM031", 1, False), ("RM032", 1, False), ("RM019", 3, False)],
    "MENU018": [("RM040", 90, True), ("RM037", 40, True), ("RM026", 60, False), ("RM030", 20, False)],
    "MENU019": [("RM007", 3, True), ("RM025", 20, True), ("RM026", 160, False), ("RM037", 25, False), ("RM028", 20, False)],
    "MENU020": [("RM038", 100, True), ("RM027", 130, True), ("RM028", 20, False), ("RM037", 12, False)],
}


HOLIDAYS = {
    date(2025, 10, 21): ("Diwali", 1.90),
    date(2025, 11, 1): ("Kannada Rajyotsava", 1.25),
    date(2025, 12, 25): ("Christmas", 1.30),
    date(2026, 1, 1): ("New Year", 1.70),
    date(2026, 1, 14): ("Makar Sankranti", 1.25),
    date(2026, 1, 26): ("Republic Day", 1.55),
}


def create_raw_material_inventory() -> List[Dict[str, str]]:
    category_supplier_map = {
        "Proteins": ["SUP001", "SUP002"],
        "Vegetables": ["SUP003", "SUP004"],
        "Dairy": ["SUP005", "SUP006"],
        "Bakery": ["SUP007", "SUP008"],
        "Spices": ["SUP009", "SUP010"],
        "Beverages": ["SUP011"],
        "Oils": ["SUP012", "SUP010"],
    }
    lead_time_map = {
        "Vegetables": (1, 2),
        "Proteins": (2, 3),
        "Dairy": (2, 3),
        "Bakery": (1, 2),
        "Spices": (5, 7),
        "Beverages": (5, 7),
        "Oils": (5, 7),
    }

    rows: List[Dict[str, str]] = []
    for idx, seed in enumerate(MATERIALS, start=1):
        material_id = f"RM{idx:03d}"
        if seed.unit == "Gram":
            max_stock = RNG.randint(12000, 65000)
        elif seed.unit == "Piece":
            max_stock = RNG.randint(300, 2800)
        elif seed.unit in {"ML", "Litre"}:
            max_stock = RNG.randint(9000, 55000)
        else:
            max_stock = RNG.randint(1000, 5000)

        reorder_level = max(1, round(max_stock * RNG.uniform(0.20, 0.30)))
        reorder_qty = max(1, round(max_stock * RNG.uniform(0.40, 0.65)))
        current_stock = max(0, round(max_stock * RNG.uniform(0.35, 0.70)))
        if current_stock > max_stock:
            current_stock = max_stock
        if reorder_level >= max_stock:
            reorder_level = max_stock - 1

        lead_low, lead_high = lead_time_map[seed.category]
        lead_time_days = RNG.randint(lead_low, lead_high)
        shelf_life_days = RNG.randint(2, 7) if seed.is_perishable else RNG.randint(45, 365)
        storage_temp_c = 4 if seed.is_perishable else 25

        created_at = (date(2024, 1, 10) + timedelta(days=RNG.randint(0, 120))).isoformat()
        last_restock_date = (END_DATE - timedelta(days=RNG.randint(0, 12))).isoformat()
        supplier_id = RNG.choice(category_supplier_map[seed.category])

        rows.append(
            {
                "material_id": material_id,
                "material_name": seed.name,
                "category": seed.category,
                "unit": seed.unit,
                "unit_cost_inr": str(seed.unit_cost_inr),
                "reorder_level": str(reorder_level),
                "reorder_qty": str(reorder_qty),
                "current_stock": str(current_stock),
                "max_stock": str(max_stock),
                "lead_time_days": str(lead_time_days),
                "shelf_life_days": str(shelf_life_days),
                "storage_temp_c": str(storage_temp_c),
                "is_perishable": bool_str(seed.is_perishable),
                "supplier_id": supplier_id,
                "last_restock_date": last_restock_date,
                "created_at": created_at,
            }
        )

    return rows


def create_menu_items() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for item in MENU_ITEMS:
        rows.append(
            {
                "menu_item_id": item.menu_item_id,
                "name": item.name,
                "category": item.category,
                "price_inr": str(item.price_inr),
                "description": item.description,
                "prep_type": item.prep_type,
                "tags": item.tags,
                "is_available": bool_str(item.is_available),
                "popularity_score": str(item.popularity_score),
                "created_at": item.created_at,
            }
        )
    return rows


def create_recipe_bom(menu_rows: List[Dict[str, str]], material_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    menu_name_lookup = {row["menu_item_id"]: row["name"] for row in menu_rows}
    material_lookup = {row["material_id"]: row for row in material_rows}
    rows: List[Dict[str, str]] = []

    for menu_id, ingredients in RECIPES.items():
        assert 3 <= len(ingredients) <= 8, f"{menu_id} must have 3-8 ingredients"
        assert any(is_critical for _, _, is_critical in ingredients), f"{menu_id} needs at least one critical ingredient"

        for material_id, quantity_per_serving, is_critical in ingredients:
            material = material_lookup[material_id]
            rows.append(
                {
                    "menu_item_id": menu_id,
                    "menu_item_name": menu_name_lookup[menu_id],
                    "material_id": material_id,
                    "material_name": material["material_name"],
                    "quantity_per_serving": str(quantity_per_serving),
                    "unit": material["unit"],
                    "is_critical": bool_str(is_critical),
                }
            )

    return rows


def daily_base_orders(day: date) -> int:
    min_orders, max_orders = weekday_order_bounds(day.weekday())
    base = RNG.randint(min_orders, max_orders)

    holiday = HOLIDAYS.get(day)
    if holiday:
        _, multiplier = holiday
        base = int(round(base * multiplier))

    return base


def weekday_order_bounds(weekday: int) -> tuple[int, int]:
    if weekday in (0, 1):
        return 40, 50
    if weekday in (2, 3):
        return 60, 70
    return 90, 130


def rebalance_daily_counts(dates: List[date], counts: List[int]) -> List[int]:
    total_orders = sum(counts)
    if MIN_ORDERS <= total_orders <= MAX_ORDERS:
        return counts

    non_holiday_indices = [idx for idx, day in enumerate(dates) if day not in HOLIDAYS]
    holiday_indices = [idx for idx, day in enumerate(dates) if day in HOLIDAYS]

    if total_orders > MAX_ORDERS:
        to_trim = total_orders - MAX_ORDERS
        while to_trim > 0:
            changed = False
            for group in (non_holiday_indices, holiday_indices):
                shuffled = list(group)
                RNG.shuffle(shuffled)
                for idx in shuffled:
                    day = dates[idx]
                    min_orders, _ = weekday_order_bounds(day.weekday())
                    min_allowed = int(round(min_orders * 1.2)) if day in HOLIDAYS else min_orders
                    if counts[idx] > min_allowed:
                        counts[idx] -= 1
                        to_trim -= 1
                        changed = True
                        if to_trim == 0:
                            break
                if to_trim == 0:
                    break
            if not changed:
                break
        return counts

    to_add = MIN_ORDERS - total_orders
    weekend_first = sorted(
        range(len(dates)),
        key=lambda idx: (dates[idx].weekday() < 4, dates[idx]),
    )
    while to_add > 0:
        changed = False
        for idx in weekend_first:
            day = dates[idx]
            _, max_orders = weekday_order_bounds(day.weekday())
            max_allowed = int(round(max_orders * 2.0)) if day in HOLIDAYS else max_orders
            if counts[idx] < max_allowed:
                counts[idx] += 1
                to_add -= 1
                changed = True
                if to_add == 0:
                    break
        if not changed:
            break
    return counts


def sample_order_time() -> tuple[str, int]:
    bucket = RNG.random()
    if bucket < 0.10:
        hour = 11
    elif bucket < 0.45:
        hour = RNG.choice([12, 13])
    elif bucket < 0.60:
        hour = RNG.choice([14, 15, 16])
    elif bucket < 0.85:
        hour = RNG.choice([19, 20])
    else:
        hour = 21

    minute = RNG.randint(0, 59)
    second = RNG.randint(0, 59)
    return f"{hour:02d}:{minute:02d}:{second:02d}", hour


def sample_quantity() -> int:
    roll = RNG.random()
    if roll < 0.70:
        return 1
    if roll < 0.95:
        return 2
    if roll < 0.99:
        return 3
    return RNG.randint(4, 5)


def pick_order_items(
    main_ids: Sequence[str],
    starter_ids: Sequence[str],
    beverage_ids: Sequence[str],
    dessert_ids: Sequence[str],
    weights: Dict[str, float],
) -> List[str]:
    pattern = RNG.random()
    mains_weights = [weights[item] for item in main_ids]
    starter_weights = [weights[item] for item in starter_ids]
    beverage_weights = [weights[item] for item in beverage_ids]
    dessert_weights = [weights[item] for item in dessert_ids]

    if pattern < 0.40:
        items = [
            choose_weighted(main_ids, mains_weights),
            choose_weighted(beverage_ids, beverage_weights),
        ]
        if RNG.random() < 0.07:
            items.append(choose_weighted(dessert_ids, dessert_weights))
        return items

    if pattern < 0.70:
        items = [
            choose_weighted(main_ids, mains_weights),
            choose_weighted(starter_ids, starter_weights),
        ]
        if RNG.random() < 0.05:
            items.append(choose_weighted(beverage_ids, beverage_weights))
        return items

    if pattern < 0.90:
        if RNG.random() < 0.10:
            return [choose_weighted(dessert_ids, dessert_weights)]
        return [choose_weighted(main_ids, mains_weights)]

    return choose_weighted_unique(main_ids, mains_weights, 2)


def create_orders_and_line_items(
    menu_rows: List[Dict[str, str]],
    recipe_rows: List[Dict[str, str]],
) -> tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    menu_lookup = {row["menu_item_id"]: row for row in menu_rows}

    recipe_by_menu: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in recipe_rows:
        recipe_by_menu[row["menu_item_id"]].append(row)

    main_ids = [row["menu_item_id"] for row in menu_rows if row["category"] == "Main Course"]
    starter_ids = [row["menu_item_id"] for row in menu_rows if row["category"] == "Starters"]
    beverage_ids = [row["menu_item_id"] for row in menu_rows if row["category"] == "Beverages"]
    dessert_ids = [row["menu_item_id"] for row in menu_rows if row["category"] == "Desserts"]

    weights = {
        row["menu_item_id"]: float(int(row["popularity_score"]) ** 1.7) for row in menu_rows
    }

    dates = list(daterange(START_DATE, END_DATE))
    daily_counts = [daily_base_orders(day) for day in dates]
    daily_counts = rebalance_daily_counts(dates, daily_counts)

    orders: List[Dict[str, str]] = []
    line_items: List[Dict[str, str]] = []
    consumption_candidates: List[Dict[str, str]] = []
    notes_pool = [
        "No onions",
        "Less spicy",
        "Extra spicy",
        "No mayo",
        "Pack separately",
        "No sugar",
        "Extra lemon",
    ]

    order_index = 1
    item_index = 1
    for day, day_orders in zip(dates, daily_counts):
        sampled_times = [sample_order_time() for _ in range(day_orders)]
        sampled_times.sort(key=lambda value: value[0])

        for sequence, (time_str, order_hour) in enumerate(sampled_times, start=1):
            order_id = f"ORD{order_index:05d}"
            order_number = f"{day.isoformat()}-{sequence:03d}"
            weekday = day.weekday()
            is_weekend = weekday >= 5
            holiday_info = HOLIDAYS.get(day)
            holiday_name = holiday_info[0] if holiday_info else ""

            order_type_prob = 0.68 if order_hour in (12, 13, 19, 20) else 0.55
            if order_hour == 21:
                order_type_prob = 0.45
            order_type = "DINE_IN" if RNG.random() < order_type_prob else "TAKEAWAY"
            table_id = f"TBL{RNG.randint(1, 20):03d}" if order_type == "DINE_IN" else ""
            staff_id = f"STF{RNG.randint(1, 12):03d}"

            cancel_prob = 0.04
            if order_hour in (12, 13, 19, 20, 21):
                cancel_prob += 0.03
            if is_weekend:
                cancel_prob += 0.005
            if holiday_info:
                cancel_prob += 0.01
            status = "CANCELLED" if RNG.random() < cancel_prob else "COMPLETED"

            created_dt = datetime.strptime(
                f"{day.isoformat()}T{time_str}", "%Y-%m-%dT%H:%M:%S"
            )
            created_at = created_dt.strftime("%Y-%m-%dT%H:%M:%S")

            selected_menu_ids = pick_order_items(main_ids, starter_ids, beverage_ids, dessert_ids, weights)

            order_total = 0
            order_consumption: Dict[str, int] = defaultdict(int)
            new_line_items: List[Dict[str, str]] = []

            for menu_id in selected_menu_ids:
                quantity = sample_quantity()
                menu_item = menu_lookup[menu_id]
                note = RNG.choice(notes_pool) if RNG.random() < 0.12 else ""
                if status == "COMPLETED":
                    item_status = "READY"
                else:
                    item_status = "COOKING" if RNG.random() < 0.35 else "PENDING"

                new_line_items.append(
                    {
                        "order_item_id": f"ITEM{item_index:05d}",
                        "order_id": order_id,
                        "menu_item_id": menu_id,
                        "menu_item_name": menu_item["name"],
                        "quantity": str(quantity),
                        "price_snapshot": menu_item["price_inr"],
                        "notes": note,
                        "item_status": item_status,
                        "created_at": created_at,
                    }
                )
                item_index += 1

                order_total += int(menu_item["price_inr"]) * quantity
                if status == "COMPLETED":
                    for ingredient in recipe_by_menu[menu_id]:
                        used_qty = int(float(ingredient["quantity_per_serving"]) * quantity)
                        order_consumption[ingredient["material_id"]] += used_qty

            sent_to_kitchen_at = ""
            completed_at = ""
            if status == "COMPLETED":
                sent_dt = created_dt + timedelta(minutes=RNG.randint(1, 3), seconds=RNG.randint(0, 59))
                done_dt = sent_dt + timedelta(minutes=RNG.randint(12, 45), seconds=RNG.randint(0, 59))
                sent_to_kitchen_at = sent_dt.strftime("%Y-%m-%dT%H:%M:%S")
                completed_at = done_dt.strftime("%Y-%m-%dT%H:%M:%S")

                movement_time = done_dt.strftime("%H:%M:%S")
                for material_id, used_qty in order_consumption.items():
                    consumption_candidates.append(
                        {
                            "material_id": material_id,
                            "quantity": str(-used_qty),
                            "movement_date": day.isoformat(),
                            "movement_time": movement_time,
                            "reference_order_id": order_id,
                        }
                    )
            elif RNG.random() < 0.45:
                sent_dt = created_dt + timedelta(minutes=RNG.randint(1, 5), seconds=RNG.randint(0, 59))
                sent_to_kitchen_at = sent_dt.strftime("%Y-%m-%dT%H:%M:%S")

            orders.append(
                {
                    "order_id": order_id,
                    "order_number": order_number,
                    "order_date": day.isoformat(),
                    "order_time": time_str,
                    "order_hour": str(order_hour),
                    "order_weekday": str(weekday),
                    "is_weekend": bool_str(is_weekend),
                    "is_holiday": bool_str(holiday_info is not None),
                    "holiday_name": holiday_name,
                    "order_type": order_type,
                    "table_id": table_id,
                    "staff_id": staff_id,
                    "status": status,
                    "total_amount": str(order_total),
                    "created_at": created_at,
                    "sent_to_kitchen_at": sent_to_kitchen_at,
                    "completed_at": completed_at,
                }
            )
            line_items.extend(new_line_items)
            order_index += 1

    return orders, line_items, consumption_candidates


def create_stock_movements(
    material_rows: List[Dict[str, str]],
    consumption_candidates: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    material_lookup = {row["material_id"]: row for row in material_rows}
    perishable_materials = [
        row for row in material_rows if row["is_perishable"] == "TRUE"
    ]

    if len(consumption_candidates) < TARGET_CONSUMPTION_MOVES:
        raise ValueError("Not enough consumption candidates to build stock movements.")

    movements_payload: List[Dict[str, str]] = []

    sampled_consumption = RNG.sample(consumption_candidates, TARGET_CONSUMPTION_MOVES)
    for sample in sampled_consumption:
        material = material_lookup[sample["material_id"]]
        movements_payload.append(
            {
                "material_id": sample["material_id"],
                "material_name": material["material_name"],
                "movement_type": "CONSUMPTION",
                "quantity": sample["quantity"],
                "movement_date": sample["movement_date"],
                "movement_time": sample["movement_time"],
                "reference_order_id": sample["reference_order_id"],
                "notes": f"Used for order {sample['reference_order_id']}",
                "created_by": "SYSTEM",
                "created_at": f"{sample['movement_date']}T{sample['movement_time']}",
            }
        )

    for _ in range(TARGET_RESTOCK_MOVES):
        material = RNG.choice(material_rows)
        reorder_qty = int(material["reorder_qty"])
        qty = max(1, int(round(reorder_qty * RNG.uniform(0.85, 1.25))))
        move_date = random_date(START_DATE, END_DATE).isoformat()
        move_time = random_time_str(6, 10)
        movements_payload.append(
            {
                "material_id": material["material_id"],
                "material_name": material["material_name"],
                "movement_type": "RESTOCK",
                "quantity": str(qty),
                "movement_date": move_date,
                "movement_time": move_time,
                "reference_order_id": "",
                "notes": "Scheduled supplier restock",
                "created_by": f"STF{RNG.randint(1, 12):03d}",
                "created_at": f"{move_date}T{move_time}",
            }
        )

    waste_notes = [
        "Expired in cold storage",
        "Quality check rejection",
        "Damaged during prep",
        "Spoilage due to delay",
    ]
    for _ in range(TARGET_WASTE_MOVES):
        material = RNG.choice(perishable_materials)
        reorder_qty = int(material["reorder_qty"])
        qty = -max(1, int(round(reorder_qty * RNG.uniform(0.02, 0.08))))
        move_date = random_date(START_DATE, END_DATE).isoformat()
        move_time = random_time_str(9, 12)
        movements_payload.append(
            {
                "material_id": material["material_id"],
                "material_name": material["material_name"],
                "movement_type": "WASTE",
                "quantity": str(qty),
                "movement_date": move_date,
                "movement_time": move_time,
                "reference_order_id": "",
                "notes": RNG.choice(waste_notes),
                "created_by": f"STF{RNG.randint(1, 12):03d}",
                "created_at": f"{move_date}T{move_time}",
            }
        )

    for _ in range(TARGET_ADJUSTMENT_MOVES):
        material = RNG.choice(material_rows)
        max_stock = int(material["max_stock"])
        delta = max(1, int(round(max_stock * RNG.uniform(0.005, 0.02))))
        if RNG.random() < 0.5:
            delta = -delta
        move_date = random_date(START_DATE, END_DATE).isoformat()
        move_time = random_time_str(8, 11)
        movements_payload.append(
            {
                "material_id": material["material_id"],
                "material_name": material["material_name"],
                "movement_type": "ADJUSTMENT",
                "quantity": str(delta),
                "movement_date": move_date,
                "movement_time": move_time,
                "reference_order_id": "",
                "notes": "Cycle count correction",
                "created_by": f"STF{RNG.randint(1, 12):03d}",
                "created_at": f"{move_date}T{move_time}",
            }
        )

    movements_payload.sort(key=lambda row: (row["movement_date"], row["movement_time"], row["movement_type"]))

    rows: List[Dict[str, str]] = []
    for idx, movement in enumerate(movements_payload, start=1):
        rows.append({"movement_id": f"MOV{idx:05d}", **movement})

    return rows


def write_csv(file_path: Path, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    with file_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def validate_dataset(
    menu_rows: List[Dict[str, str]],
    recipe_rows: List[Dict[str, str]],
    material_rows: List[Dict[str, str]],
    order_rows: List[Dict[str, str]],
    order_item_rows: List[Dict[str, str]],
    movement_rows: List[Dict[str, str]],
    supplier_rows: List[Dict[str, str]],
) -> None:
    assert 15 <= len(menu_rows) <= 25
    assert 45 <= len(recipe_rows) <= 150
    assert 30 <= len(material_rows) <= 50
    assert MIN_ORDERS <= len(order_rows) <= MAX_ORDERS
    assert 12000 <= len(order_item_rows) <= 20000
    assert 500 <= len(movement_rows) <= 800
    assert 10 <= len(supplier_rows) <= 15

    menu_ids = {row["menu_item_id"] for row in menu_rows}
    material_ids = {row["material_id"] for row in material_rows}
    order_ids = {row["order_id"] for row in order_rows}

    for row in recipe_rows:
        assert row["menu_item_id"] in menu_ids
        assert row["material_id"] in material_ids

    for row in order_item_rows:
        assert row["order_id"] in order_ids
        assert row["menu_item_id"] in menu_ids
        assert 1 <= int(row["quantity"]) <= 10

    recipe_count_by_menu = Counter(row["menu_item_id"] for row in recipe_rows)
    assert all(3 <= count <= 8 for count in recipe_count_by_menu.values())

    totals_by_order = defaultdict(int)
    for item in order_item_rows:
        totals_by_order[item["order_id"]] += int(item["quantity"]) * int(item["price_snapshot"])

    for order in order_rows:
        assert totals_by_order[order["order_id"]] == int(order["total_amount"])

    avg_items_per_order = len(order_item_rows) / len(order_rows)
    assert 1.5 <= avg_items_per_order <= 2.5

    cancellations = sum(1 for row in order_rows if row["status"] == "CANCELLED")
    cancel_rate = cancellations / len(order_rows)
    assert 0.05 <= cancel_rate <= 0.08

    daily_counts = Counter(row["order_date"] for row in order_rows)
    for order_day, count in daily_counts.items():
        as_date = datetime.strptime(order_day, "%Y-%m-%d").date()
        min_orders, max_orders = weekday_order_bounds(as_date.weekday())
        if as_date in HOLIDAYS:
            assert count >= int(round(min_orders * 1.2))
        else:
            assert min_orders <= count <= max_orders

    qty_counter = Counter(int(row["quantity"]) for row in order_item_rows)
    qty_total = len(order_item_rows)
    qty_one_ratio = qty_counter[1] / qty_total
    qty_two_ratio = qty_counter[2] / qty_total
    qty_three_plus_ratio = sum(v for k, v in qty_counter.items() if k >= 3) / qty_total

    assert qty_one_ratio >= 0.65
    assert qty_two_ratio >= 0.20
    assert qty_three_plus_ratio >= 0.03

    movement_types = Counter(row["movement_type"] for row in movement_rows)
    assert movement_types["CONSUMPTION"] == TARGET_CONSUMPTION_MOVES
    assert movement_types["RESTOCK"] == TARGET_RESTOCK_MOVES
    assert movement_types["WASTE"] == TARGET_WASTE_MOVES
    assert movement_types["ADJUSTMENT"] == TARGET_ADJUSTMENT_MOVES

    hour_counts = Counter(int(row["order_hour"]) for row in order_rows)
    morning = hour_counts[11] / len(order_rows)
    lunch = (hour_counts[12] + hour_counts[13]) / len(order_rows)
    afternoon = (hour_counts[14] + hour_counts[15] + hour_counts[16]) / len(order_rows)
    dinner = (hour_counts[19] + hour_counts[20]) / len(order_rows)
    late = hour_counts[21] / len(order_rows)
    assert 0.08 <= morning <= 0.13
    assert 0.30 <= lunch <= 0.40
    assert 0.12 <= afternoon <= 0.18
    assert 0.20 <= dinner <= 0.30
    assert 0.12 <= late <= 0.18

    print("Validation passed.")
    print(f"menu_items.csv rows: {len(menu_rows)}")
    print(f"recipe_bom.csv rows: {len(recipe_rows)}")
    print(f"raw_material_inventory.csv rows: {len(material_rows)}")
    print(f"orders.csv rows: {len(order_rows)}")
    print(f"order_line_items.csv rows: {len(order_item_rows)}")
    print(f"stock_movement_log.csv rows: {len(movement_rows)}")
    print(f"supplier_master.csv rows: {len(supplier_rows)}")
    print(f"Average items/order: {avg_items_per_order:.3f}")
    print(f"Cancellation rate: {cancel_rate:.3%}")
    print(
        "Hour distribution:"
        f" morning={morning:.1%}, lunch={lunch:.1%}, afternoon={afternoon:.1%}, dinner={dinner:.1%}, late={late:.1%}"
    )
    print(
        "Qty distribution:"
        f" qty1={qty_one_ratio:.1%}, qty2={qty_two_ratio:.1%}, qty3+={qty_three_plus_ratio:.1%}"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    supplier_rows = SUPPLIERS
    material_rows = create_raw_material_inventory()
    menu_rows = create_menu_items()
    recipe_rows = create_recipe_bom(menu_rows, material_rows)
    order_rows, order_item_rows, consumption_candidates = create_orders_and_line_items(menu_rows, recipe_rows)
    movement_rows = create_stock_movements(material_rows, consumption_candidates)

    write_csv(
        OUTPUT_DIR / "menu_items.csv",
        [
            "menu_item_id",
            "name",
            "category",
            "price_inr",
            "description",
            "prep_type",
            "tags",
            "is_available",
            "popularity_score",
            "created_at",
        ],
        menu_rows,
    )
    write_csv(
        OUTPUT_DIR / "recipe_bom.csv",
        [
            "menu_item_id",
            "menu_item_name",
            "material_id",
            "material_name",
            "quantity_per_serving",
            "unit",
            "is_critical",
        ],
        recipe_rows,
    )
    write_csv(
        OUTPUT_DIR / "raw_material_inventory.csv",
        [
            "material_id",
            "material_name",
            "category",
            "unit",
            "unit_cost_inr",
            "reorder_level",
            "reorder_qty",
            "current_stock",
            "max_stock",
            "lead_time_days",
            "shelf_life_days",
            "storage_temp_c",
            "is_perishable",
            "supplier_id",
            "last_restock_date",
            "created_at",
        ],
        material_rows,
    )
    write_csv(
        OUTPUT_DIR / "orders.csv",
        [
            "order_id",
            "order_number",
            "order_date",
            "order_time",
            "order_hour",
            "order_weekday",
            "is_weekend",
            "is_holiday",
            "holiday_name",
            "order_type",
            "table_id",
            "staff_id",
            "status",
            "total_amount",
            "created_at",
            "sent_to_kitchen_at",
            "completed_at",
        ],
        order_rows,
    )
    write_csv(
        OUTPUT_DIR / "order_line_items.csv",
        [
            "order_item_id",
            "order_id",
            "menu_item_id",
            "menu_item_name",
            "quantity",
            "price_snapshot",
            "notes",
            "item_status",
            "created_at",
        ],
        order_item_rows,
    )
    write_csv(
        OUTPUT_DIR / "stock_movement_log.csv",
        [
            "movement_id",
            "material_id",
            "material_name",
            "movement_type",
            "quantity",
            "movement_date",
            "movement_time",
            "reference_order_id",
            "notes",
            "created_by",
            "created_at",
        ],
        movement_rows,
    )
    write_csv(
        OUTPUT_DIR / "supplier_master.csv",
        [
            "supplier_id",
            "supplier_name",
            "contact_person",
            "phone",
            "email",
            "address",
            "city",
            "state",
            "pincode",
            "payment_terms",
            "is_active",
            "created_at",
        ],
        supplier_rows,
    )

    validate_dataset(
        menu_rows,
        recipe_rows,
        material_rows,
        order_rows,
        order_item_rows,
        movement_rows,
        supplier_rows,
    )


if __name__ == "__main__":
    main()

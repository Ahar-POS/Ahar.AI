"""
Generate 100 days of realistic test data for ML training (Nov 26, 2025 → Mar 4, 2026)

This script generates synthetic restaurant data following realistic patterns from
actual restaurant operations, including orders, promotions, inventory movements,
wastage, and stock-outs.
"""

import csv
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from collections import defaultdict
import json

# Set random seed for reproducibility
random.seed(42)
np.random.seed(42)

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

START_DATE = datetime(2025, 11, 26)
END_DATE = datetime(2026, 3, 4)
TOTAL_DAYS = (END_DATE - START_DATE).days + 1

# Order volume patterns from Lexi's data
MEAN_DAILY_ORDERS = 87
STD_DAILY_ORDERS = 15
MIN_DAILY_ORDERS = 60
MAX_DAILY_ORDERS = 120

# Order value patterns
MEAN_AOV = 85000  # ₹850 in paise
STD_AOV = 46400   # ₹464 in paise

# Time distribution (hourly patterns) - bimodal distribution
HOURLY_DISTRIBUTION = {
    11: 0.02,
    12: 0.06,
    13: 0.09,
    14: 0.14,  # Lunch peak
    15: 0.08,
    16: 0.07,
    17: 0.08,
    18: 0.09,
    19: 0.16,  # Dinner peak
    20: 0.14,  # Dinner peak
    21: 0.05,
    22: 0.02,
}

# Weekend patterns
WEEKEND_VOLUME_MODIFIER = 0.85  # -15% volume
WEEKEND_AOV_MODIFIER = 1.06     # +6% AOV

# Holiday patterns
HOLIDAY_VOLUME_MODIFIER = 1.50  # +50% orders
HOLIDAY_AOV_MODIFIER = 1.20     # +20% AOV

# Holidays in the date range
HOLIDAYS = [
    (datetime(2025, 12, 25), "Christmas"),
    (datetime(2026, 1, 1), "New Year"),
    (datetime(2026, 1, 14), "Sankranti"),
    (datetime(2026, 1, 26), "Republic Day"),
]

# Menu item popularity (power law distribution)
# Top 5 items = 50% of volume
ITEM_POPULARITY_WEIGHTS = {
    'MENU005': 0.18,  # Masala Dosa (most popular)
    'MENU001': 0.12,  # Smoky Chicken Burger
    'MENU004': 0.10,  # Chicken Rice Bowl
    'MENU014': 0.08,  # Mango Lassi
    'MENU010': 0.07,  # French Fries
    'MENU002': 0.06,  # Paneer Tikka Wrap
    'MENU003': 0.05,  # Veggie Club Sandwich
    'MENU007': 0.05,  # Veg Hakka Noodles
    'MENU006': 0.04,  # Grilled Fish Wrap
    'MENU008': 0.04,  # Egg Bhurji Roll
    'MENU009': 0.03,  # Paneer Butter Rice
    'MENU015': 0.03,  # Masala Lemonade
    'MENU011': 0.03,  # Chili Potato
    'MENU012': 0.03,  # Crispy Chicken Bites
    'MENU016': 0.03,  # Cold Coffee
    'MENU013': 0.02,  # Garlic Bread Sticks
    'MENU018': 0.02,  # Gulab Jamun
    'MENU017': 0.01,  # Spiced Buttermilk
    'MENU020': 0.01,  # Mango Yogurt Cup
    'MENU019': 0.00,  # Bread Butter Pudding (not available)
}

# Order composition
MEAN_ITEMS_PER_ORDER = 1.73
STD_ITEMS_PER_ORDER = 0.9

# Order type distribution
ORDER_TYPE_DISTRIBUTION = {
    'TAKEAWAY': 0.70,
    'DINE_IN': 0.24,
    'DELIVERY': 0.06,
}

# Wastage patterns
BASE_WASTAGE_RATE = 0.065  # 6.5% average
MONDAY_WASTAGE_RATE = 0.11  # Higher on Mondays
PERISHABLE_WASTAGE_BONUS = 0.03

# Stock-out probability
STOCKOUT_PROBABILITY_PER_MONTH = 0.20  # 20% chance per month
STOCKOUT_MEAN_ORDERS_AFFECTED = 5

# Restock patterns
RESTOCK_THRESHOLD = 0.30  # Restock when stock < 30% of max
RESTOCK_TARGET = 0.85     # Restock to 85% of max

# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

def load_menu_items() -> pd.DataFrame:
    """Load menu items from CSV"""
    return pd.read_csv('menu_items.csv')

def load_recipe_bom() -> pd.DataFrame:
    """Load recipe bill of materials"""
    return pd.read_csv('recipe_bom.csv')

def load_inventory() -> pd.DataFrame:
    """Load raw material inventory"""
    return pd.read_csv('raw_material_inventory.csv')

# ============================================================================
# DATE AND TIME UTILITIES
# ============================================================================

def is_weekend(date: datetime) -> bool:
    """Check if date is Saturday (5) or Sunday (6)"""
    return date.weekday() in [5, 6]

def is_holiday(date: datetime) -> Tuple[bool, str]:
    """Check if date is a holiday"""
    for holiday_date, name in HOLIDAYS:
        if holiday_date.date() == date.date():
            return True, name
    return False, ""

def get_order_hour() -> int:
    """Generate order hour based on bimodal distribution"""
    hours = list(HOURLY_DISTRIBUTION.keys())
    probs = list(HOURLY_DISTRIBUTION.values())
    return np.random.choice(hours, p=probs)

def get_order_time(hour: int) -> str:
    """Generate order time for a given hour"""
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return f"{hour:02d}:{minute:02d}:{second:02d}"

# ============================================================================
# PROMOTION GENERATION
# ============================================================================

def generate_promotions() -> List[Dict]:
    """Generate 8-10 promotion events over 100 days"""
    promotions = []
    promo_id = 1

    current_date = START_DATE

    # Weekend specials (every 3rd weekend)
    weekend_count = 0
    while current_date <= END_DATE:
        if is_weekend(current_date):
            weekend_count += 1
            if weekend_count % 3 == 0:
                promotions.append({
                    'promo_id': f'PROMO{promo_id:03d}',
                    'start_date': current_date.strftime('%Y-%m-%d'),
                    'end_date': (current_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                    'promo_type': 'WEEKEND_SPECIAL',
                    'menu_item_ids': 'MENU005,MENU010,MENU011',  # Dosa, Fries, Chili Potato
                    'discount_pct': 15,
                    'description': 'Weekend Special - 15% off on selected items',
                    'demand_boost': 1.30,  # +30% for promoted items
                })
                promo_id += 1
        current_date += timedelta(days=1)

    # Holiday specials
    for holiday_date, holiday_name in HOLIDAYS:
        if START_DATE <= holiday_date <= END_DATE:
            promotions.append({
                'promo_id': f'PROMO{promo_id:03d}',
                'start_date': holiday_date.strftime('%Y-%m-%d'),
                'end_date': holiday_date.strftime('%Y-%m-%d'),
                'promo_type': 'HOLIDAY_SPECIAL',
                'menu_item_ids': 'ALL',
                'discount_pct': 20,
                'description': f'{holiday_name} Special - 20% off on all items',
                'demand_boost': 1.40,
            })
            promo_id += 1

    # Mid-week combos (random Wednesdays)
    current_date = START_DATE
    while current_date <= END_DATE:
        if current_date.weekday() == 2 and random.random() < 0.3:  # 30% of Wednesdays
            promotions.append({
                'promo_id': f'PROMO{promo_id:03d}',
                'start_date': current_date.strftime('%Y-%m-%d'),
                'end_date': current_date.strftime('%Y-%m-%d'),
                'promo_type': 'MIDWEEK_COMBO',
                'menu_item_ids': 'MENU001,MENU004,MENU007',  # Burger, Rice Bowl, Noodles
                'discount_pct': 10,
                'description': 'Wednesday Combo - Buy 1 Get 1 on combo items',
                'demand_boost': 1.35,
            })
            promo_id += 1
        current_date += timedelta(days=1)

    return promotions

def get_active_promotions(date: datetime, promotions: List[Dict]) -> List[Dict]:
    """Get promotions active on a given date"""
    date_str = date.strftime('%Y-%m-%d')
    active = []
    for promo in promotions:
        if promo['start_date'] <= date_str <= promo['end_date']:
            active.append(promo)
    return active

def apply_promotion_boost(
    base_weights: Dict[str, float],
    promotions: List[Dict]
) -> Dict[str, float]:
    """Apply promotion boost to item selection weights"""
    weights = base_weights.copy()

    for promo in promotions:
        if promo['menu_item_ids'] == 'ALL':
            # All items get a boost
            for item_id in weights:
                weights[item_id] *= promo['demand_boost']
        else:
            # Specific items get a boost
            promoted_items = promo['menu_item_ids'].split(',')
            for item_id in promoted_items:
                if item_id in weights:
                    weights[item_id] *= promo['demand_boost']

    # Normalize weights
    total = sum(weights.values())
    return {k: v/total for k, v in weights.items()}

# ============================================================================
# ORDER GENERATION
# ============================================================================

def generate_daily_order_count(date: datetime, has_promotion: bool = False) -> int:
    """Generate order count for a given day"""
    base_count = max(MIN_DAILY_ORDERS,
                     min(MAX_DAILY_ORDERS,
                         int(np.random.normal(MEAN_DAILY_ORDERS, STD_DAILY_ORDERS))))

    # Apply weekend modifier
    if is_weekend(date):
        base_count = int(base_count * WEEKEND_VOLUME_MODIFIER)

    # Apply holiday modifier
    is_hol, _ = is_holiday(date)
    if is_hol:
        base_count = int(base_count * HOLIDAY_VOLUME_MODIFIER)

    # Apply promotion modifier
    if has_promotion:
        base_count = int(base_count * 1.25)  # +25% orders on promo days

    # Add slight growth trend over 100 days (+10% total)
    days_elapsed = (date - START_DATE).days
    growth_factor = 1.0 + (0.10 * days_elapsed / TOTAL_DAYS)
    base_count = int(base_count * growth_factor)

    return max(MIN_DAILY_ORDERS, min(MAX_DAILY_ORDERS, base_count))

def generate_order_items(
    menu_items: pd.DataFrame,
    item_weights: Dict[str, float]
) -> List[Dict]:
    """Generate items for a single order"""
    # Determine number of items (log-normal distribution)
    num_items = max(1, int(np.random.lognormal(
        mean=np.log(MEAN_ITEMS_PER_ORDER),
        sigma=0.5
    )))
    num_items = min(num_items, 5)  # Cap at 5 items

    # Select items based on weights
    item_ids = list(item_weights.keys())
    probs = [item_weights[item_id] for item_id in item_ids]

    selected_items = np.random.choice(
        item_ids,
        size=num_items,
        replace=False,
        p=probs
    )

    order_items = []
    for item_id in selected_items:
        item_row = menu_items[menu_items['menu_item_id'] == item_id].iloc[0]

        # Quantity (mostly 1, occasionally 2)
        quantity = 1 if random.random() < 0.85 else 2

        order_items.append({
            'menu_item_id': item_id,
            'menu_item_name': item_row['name'],
            'quantity': quantity,
            'price_snapshot': item_row['price_inr'],
        })

    return order_items

def generate_orders(
    menu_items: pd.DataFrame,
    promotions: List[Dict]
) -> Tuple[List[Dict], List[Dict]]:
    """Generate all orders for 100 days"""
    orders = []
    order_items = []

    order_id = 1
    item_id = 1

    current_date = START_DATE

    while current_date <= END_DATE:
        # Get active promotions
        active_promos = get_active_promotions(current_date, promotions)

        # Generate order count (with promotion boost if applicable)
        daily_order_count = generate_daily_order_count(current_date, has_promotion=len(active_promos) > 0)

        # Apply promotion boost to item weights
        item_weights = apply_promotion_boost(ITEM_POPULARITY_WEIGHTS, active_promos)

        # Generate orders for this day
        for order_num in range(daily_order_count):
            # Generate order time
            order_hour = get_order_hour()
            order_time = get_order_time(order_hour)
            order_datetime = datetime.combine(current_date.date(),
                                             datetime.strptime(order_time, '%H:%M:%S').time())

            # Generate order items
            items = generate_order_items(menu_items, item_weights)

            # Calculate total
            total_amount = sum(item['price_snapshot'] * item['quantity'] for item in items)

            # Apply weekend AOV modifier
            if is_weekend(current_date):
                total_amount = int(total_amount * WEEKEND_AOV_MODIFIER)

            # Apply holiday AOV modifier
            is_hol, holiday_name = is_holiday(current_date)
            if is_hol:
                total_amount = int(total_amount * HOLIDAY_AOV_MODIFIER)

            # Order type
            order_type = np.random.choice(
                list(ORDER_TYPE_DISTRIBUTION.keys()),
                p=list(ORDER_TYPE_DISTRIBUTION.values())
            )

            # Table ID for dine-in
            table_id = f'TBL{random.randint(1, 20):03d}' if order_type == 'DINE_IN' else ''

            # Staff ID
            staff_id = f'STF{random.randint(1, 12):03d}'

            # Status (95% completed, 5% cancelled)
            status = 'COMPLETED' if random.random() < 0.95 else 'CANCELLED'

            # Order record
            order = {
                'order_id': f'ORD{order_id:05d}',
                'order_number': f'{current_date.strftime("%Y-%m-%d")}-{order_num+1:03d}',
                'order_date': current_date.strftime('%Y-%m-%d'),
                'order_time': order_time,
                'order_hour': order_hour,
                'order_weekday': current_date.weekday(),
                'is_weekend': is_weekend(current_date),
                'is_holiday': is_hol,
                'holiday_name': holiday_name if is_hol else '',
                'order_type': order_type,
                'table_id': table_id,
                'staff_id': staff_id,
                'status': status,
                'total_amount': total_amount,
                'created_at': order_datetime.isoformat(),
                'sent_to_kitchen_at': (order_datetime + timedelta(minutes=random.randint(1, 3))).isoformat() if status == 'COMPLETED' else '',
                'completed_at': (order_datetime + timedelta(minutes=random.randint(15, 45))).isoformat() if status == 'COMPLETED' else '',
            }
            orders.append(order)

            # Order items
            for item in items:
                order_item = {
                    'order_item_id': f'ITEM{item_id:05d}',
                    'order_id': order['order_id'],
                    'menu_item_id': item['menu_item_id'],
                    'menu_item_name': item['menu_item_name'],
                    'quantity': item['quantity'],
                    'price_snapshot': item['price_snapshot'],
                    'notes': '',
                    'item_status': 'READY' if status == 'COMPLETED' else 'PENDING',
                    'created_at': order_datetime.isoformat(),
                }
                order_items.append(order_item)
                item_id += 1

            order_id += 1

        current_date += timedelta(days=1)

        # Progress indicator
        progress = (current_date - START_DATE).days / TOTAL_DAYS * 100
        if (current_date - START_DATE).days % 10 == 0:
            print(f"Progress: {progress:.1f}% - Generated {len(orders)} orders")

    return orders, order_items

# ============================================================================
# INVENTORY AND CONSUMPTION TRACKING
# ============================================================================

def calculate_daily_consumption(
    orders: List[Dict],
    order_items: List[Dict],
    recipe_bom: pd.DataFrame
) -> Dict[str, Dict[str, float]]:
    """Calculate daily ingredient consumption from orders"""
    # Group orders by date
    daily_consumption = defaultdict(lambda: defaultdict(float))

    for order in orders:
        if order['status'] != 'COMPLETED':
            continue

        order_date = order['order_date']
        order_id = order['order_id']

        # Get items for this order
        items = [item for item in order_items if item['order_id'] == order_id]

        for item in items:
            menu_item_id = item['menu_item_id']
            quantity = item['quantity']

            # Get recipe for this item
            recipe = recipe_bom[recipe_bom['menu_item_id'] == menu_item_id]

            for _, ingredient in recipe.iterrows():
                material_id = ingredient['material_id']
                amount_per_serving = ingredient['quantity_per_serving']

                # Add to daily consumption
                daily_consumption[order_date][material_id] += amount_per_serving * quantity

    return daily_consumption

def generate_purchase_history(
    inventory: pd.DataFrame,
    daily_consumption: Dict[str, Dict[str, float]]
) -> List[Dict]:
    """Generate purchase/restock history based on consumption"""
    purchases = []
    purchase_id = 1

    # Initialize stock levels
    stock_levels = {}
    for _, row in inventory.iterrows():
        stock_levels[row['material_id']] = row['current_stock']

    # Track by date
    all_dates = sorted(daily_consumption.keys())

    for date in all_dates:
        consumption = daily_consumption[date]

        # Check each material
        for material_id, consumed in consumption.items():
            inv_row = inventory[inventory['material_id'] == material_id].iloc[0]
            max_stock = inv_row['max_stock']
            reorder_level = max_stock * RESTOCK_THRESHOLD
            restock_target = max_stock * RESTOCK_TARGET

            # Subtract consumption
            stock_levels[material_id] -= consumed

            # Check if restock needed
            if stock_levels[material_id] < reorder_level:
                # Generate purchase
                restock_qty = restock_target - stock_levels[material_id]
                restock_qty = max(0, restock_qty)  # Ensure non-negative

                purchases.append({
                    'purchase_id': f'PUR{purchase_id:05d}',
                    'purchase_date': date,
                    'material_id': material_id,
                    'quantity': int(restock_qty),
                    'unit_cost_inr': inv_row['unit_cost_inr'],
                    'supplier_id': inv_row['supplier_id'],
                    'total_cost': int(restock_qty * inv_row['unit_cost_inr']),
                })
                purchase_id += 1

                # Add lead time
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                delivery_date = date_obj + timedelta(days=int(inv_row['lead_time_days']))

                # Update stock on delivery date
                delivery_date_str = delivery_date.strftime('%Y-%m-%d')
                if delivery_date_str <= END_DATE.strftime('%Y-%m-%d'):
                    stock_levels[material_id] += restock_qty

    return purchases

def generate_wastage_log(
    inventory: pd.DataFrame,
    daily_consumption: Dict[str, Dict[str, float]]
) -> List[Dict]:
    """Generate wastage logs"""
    wastage_records = []

    for date, consumption in daily_consumption.items():
        date_obj = datetime.strptime(date, '%Y-%m-%d')

        # Base wastage rate
        wastage_rate = BASE_WASTAGE_RATE

        # Monday has higher wastage
        if date_obj.weekday() == 0:
            wastage_rate = MONDAY_WASTAGE_RATE

        for material_id, consumed in consumption.items():
            inv_row = inventory[inventory['material_id'] == material_id].iloc[0]

            # Perishable items have higher wastage
            if inv_row['is_perishable']:
                material_wastage_rate = wastage_rate + PERISHABLE_WASTAGE_BONUS
            else:
                material_wastage_rate = wastage_rate * 0.5  # Non-perishable has less

            # Calculate wastage
            wasted_qty = consumed * material_wastage_rate

            # Random variation
            wasted_qty *= random.uniform(0.8, 1.2)

            if wasted_qty > 0:
                # Random reason
                reason = np.random.choice(
                    ['expired', 'over_prep', 'spoilage', 'quality_issue'],
                    p=[0.40, 0.30, 0.20, 0.10]
                )

                wastage_records.append({
                    'date': date,
                    'material_id': material_id,
                    'quantity_wasted': round(wasted_qty, 2),
                    'reason': reason,
                    'cost_inr': int(wasted_qty * inv_row['unit_cost_inr']),
                })

    return wastage_records

def generate_stockout_log(
    inventory: pd.DataFrame,
    daily_consumption: Dict[str, Dict[str, float]]
) -> List[Dict]:
    """Generate stock-out events"""
    stockouts = []

    # Randomly select 6-8 dates for stock-outs
    all_dates = sorted(daily_consumption.keys())
    num_stockouts = random.randint(6, 8)
    stockout_dates = random.sample(all_dates, num_stockouts)

    for date in stockout_dates:
        # Select a random popular material
        material_id = random.choice(['RM001', 'RM003', 'RM005', 'RM009', 'RM010'])
        inv_row = inventory[inventory['material_id'] == material_id].iloc[0]

        # Estimate orders affected
        orders_affected = random.randint(3, 8)

        # Estimate revenue loss (average order value * orders)
        revenue_loss = MEAN_AOV * orders_affected

        stockouts.append({
            'date': date,
            'time': f'{random.randint(18, 21):02d}:{random.randint(0, 59):02d}:00',
            'material_id': material_id,
            'orders_affected': orders_affected,
            'menu_items_affected': 'Multiple',  # Simplified
            'estimated_revenue_loss': int(revenue_loss),
        })

    return stockouts

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    print("=" * 80)
    print("GENERATING 100 DAYS OF REALISTIC TEST DATA")
    print("=" * 80)
    print(f"Date Range: {START_DATE.strftime('%Y-%m-%d')} to {END_DATE.strftime('%Y-%m-%d')}")
    print(f"Total Days: {TOTAL_DAYS}")
    print()

    # Load existing data
    print("Loading existing reference data...")
    menu_items = load_menu_items()
    recipe_bom = load_recipe_bom()
    inventory = load_inventory()
    print(f"  Menu Items: {len(menu_items)}")
    print(f"  Recipe BOM: {len(recipe_bom)} entries")
    print(f"  Inventory: {len(inventory)} materials")
    print()

    # Generate promotions
    print("Generating promotions...")
    promotions = generate_promotions()
    print(f"  Generated {len(promotions)} promotions")
    print()

    # Generate orders
    print("Generating orders and order items...")
    orders, order_items = generate_orders(menu_items, promotions)
    print(f"  Generated {len(orders)} orders")
    print(f"  Generated {len(order_items)} order items")
    print()

    # Calculate daily consumption
    print("Calculating daily ingredient consumption...")
    daily_consumption = calculate_daily_consumption(orders, order_items, recipe_bom)
    print(f"  Tracked {len(daily_consumption)} days of consumption")
    print()

    # Generate purchase history
    print("Generating purchase/restock history...")
    purchases = generate_purchase_history(inventory, daily_consumption)
    print(f"  Generated {len(purchases)} purchase orders")
    print()

    # Generate wastage log
    print("Generating wastage logs...")
    wastage = generate_wastage_log(inventory, daily_consumption)
    print(f"  Generated {len(wastage)} wastage records")
    print()

    # Generate stock-out log
    print("Generating stock-out events...")
    stockouts = generate_stockout_log(inventory, daily_consumption)
    print(f"  Generated {len(stockouts)} stock-out events")
    print()

    # Save to CSV files
    print("Saving data to CSV files...")

    # Orders
    pd.DataFrame(orders).to_csv('orders.csv', index=False)
    print("  ✓ orders.csv")

    # Order items
    pd.DataFrame(order_items).to_csv('order_line_items.csv', index=False)
    print("  ✓ order_line_items.csv")

    # Promotions
    pd.DataFrame(promotions).to_csv('promotions.csv', index=False)
    print("  ✓ promotions.csv")

    # Purchase history
    pd.DataFrame(purchases).to_csv('purchase_history.csv', index=False)
    print("  ✓ purchase_history.csv")

    # Wastage log
    pd.DataFrame(wastage).to_csv('wastage_log.csv', index=False)
    print("  ✓ wastage_log.csv")

    # Stock-out log
    pd.DataFrame(stockouts).to_csv('stockout_log.csv', index=False)
    print("  ✓ stockout_log.csv")

    print()
    print("=" * 80)
    print("DATA GENERATION COMPLETE!")
    print("=" * 80)
    print()
    print("Summary Statistics:")
    print(f"  Total Orders: {len(orders)}")
    print(f"  Average Orders/Day: {len(orders) / TOTAL_DAYS:.1f}")
    print(f"  Total Revenue: ₹{sum(o['total_amount'] for o in orders) / 100:,.2f}")
    print(f"  Average Order Value: ₹{sum(o['total_amount'] for o in orders) / len(orders) / 100:.2f}")
    print(f"  Promotions: {len(promotions)}")
    print(f"  Purchase Orders: {len(purchases)}")
    print(f"  Wastage Events: {len(wastage)}")
    print(f"  Stock-outs: {len(stockouts)}")
    print()

if __name__ == '__main__':
    main()

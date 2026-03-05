"""
Extend test data from Jan 28, 2026 to Feb 27, 2026 (today)

Generates realistic orders for the past 30 days and appends to CSVs.
"""

import pandas as pd
import random
from datetime import datetime, timedelta
import os

# Configuration
START_DATE = datetime(2026, 1, 29)  # Day after current data ends
END_DATE = datetime(2026, 2, 27)    # Today
ORDERS_PER_DAY = 30  # Average orders per day

# Get script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def generate_extended_data():
    """Generate orders from Jan 29 to Feb 27, 2026"""

    print("=" * 80)
    print("EXTENDING TEST DATA TO TODAY")
    print("=" * 80)

    # Load existing data
    print("\n1. Loading existing data...")
    orders_df = pd.read_csv(os.path.join(SCRIPT_DIR, 'orders.csv'))
    items_df = pd.read_csv(os.path.join(SCRIPT_DIR, 'order_line_items.csv'))
    menu_df = pd.read_csv(os.path.join(SCRIPT_DIR, 'menu_items.csv'))

    print(f"   Current orders: {len(orders_df)}")
    print(f"   Current items: {len(items_df)}")
    print(f"   Latest order date: {orders_df['order_date'].max()}")

    # Get starting IDs
    last_order_num = int(orders_df['order_number'].str.split('-').str[-1].max())
    last_order_id_num = int(orders_df['order_id'].str.replace('ORD', '').max())
    last_item_id_num = int(items_df['order_item_id'].str.replace('ITEM', '').max())

    print(f"\n2. Generating new data...")
    print(f"   Date range: {START_DATE.date()} to {END_DATE.date()}")
    print(f"   Orders per day: ~{ORDERS_PER_DAY}")

    new_orders = []
    new_items = []

    current_date = START_DATE
    order_counter = last_order_num + 1
    order_id_counter = last_order_id_num + 1
    item_counter = last_item_id_num + 1

    # Generate orders for each day
    while current_date <= END_DATE:
        # Vary orders per day (weekends have more)
        is_weekend = current_date.weekday() >= 5
        daily_orders = random.randint(35, 50) if is_weekend else random.randint(20, 35)

        for _ in range(daily_orders):
            # Random order time during business hours (11 AM - 10 PM)
            hour = random.randint(11, 21)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            order_time = current_date.replace(hour=hour, minute=minute, second=second)

            # Order details
            order_type = random.choice(['dine_in'] * 7 + ['takeaway'] * 3)  # 70% dine-in
            table_id = f"TBL{random.randint(1, 12):02d}" if order_type == 'dine_in' else None
            staff_id = f"STAFF{random.randint(1, 5):02d}"
            status = 'COMPLETED'  # All historical orders are completed

            # Select 1-4 menu items
            num_items = random.choices([1, 2, 3, 4], weights=[0.3, 0.4, 0.2, 0.1])[0]
            selected_items = menu_df.sample(n=num_items)

            order_total = 0
            order_items = []

            for _, menu_item in selected_items.iterrows():
                quantity = random.randint(1, 2)
                price_snapshot = menu_item['price_inr']
                item_total = price_snapshot * quantity
                order_total += item_total

                # Create order item
                order_items.append({
                    'order_item_id': f"ITEM{item_counter:08d}",
                    'order_id': f"ORD{order_id_counter:08d}",
                    'menu_item_id': menu_item['menu_item_id'],
                    'menu_item_name': menu_item['name'],
                    'quantity': quantity,
                    'price_snapshot': price_snapshot,
                    'notes': None,
                    'item_status': 'READY',
                    'created_at': order_time.isoformat()
                })
                item_counter += 1

            # Create order
            order_number_str = f"{current_date.strftime('%Y-%m-%d')}-{order_counter % 1000:03d}"

            new_orders.append({
                'order_id': f"ORD{order_id_counter:08d}",
                'order_number': order_number_str,
                'order_date': current_date.strftime('%Y-%m-%d'),
                'order_time': order_time.strftime('%H:%M:%S'),
                'order_hour': hour,
                'order_weekday': current_date.weekday(),
                'is_weekend': is_weekend,
                'is_holiday': False,
                'holiday_name': None,
                'order_type': order_type,
                'table_id': table_id,
                'staff_id': staff_id,
                'status': status,
                'total_amount': order_total,
                'created_at': order_time.isoformat(),
                'sent_to_kitchen_at': (order_time + timedelta(seconds=30)).isoformat(),
                'completed_at': (order_time + timedelta(minutes=random.randint(15, 45))).isoformat()
            })

            new_items.extend(order_items)

            order_counter += 1
            order_id_counter += 1

        current_date += timedelta(days=1)

    print(f"   Generated {len(new_orders)} new orders")
    print(f"   Generated {len(new_items)} new items")

    # Append to existing data
    print("\n3. Appending to CSV files...")

    new_orders_df = pd.DataFrame(new_orders)
    new_items_df = pd.DataFrame(new_items)

    # Append to files
    combined_orders = pd.concat([orders_df, new_orders_df], ignore_index=True)
    combined_items = pd.concat([items_df, new_items_df], ignore_index=True)

    # Save
    combined_orders.to_csv(os.path.join(SCRIPT_DIR, 'orders.csv'), index=False)
    combined_items.to_csv(os.path.join(SCRIPT_DIR, 'order_line_items.csv'), index=False)

    print(f"   ✓ Updated orders.csv ({len(combined_orders)} total orders)")
    print(f"   ✓ Updated order_line_items.csv ({len(combined_items)} total items)")

    # Summary
    print("\n" + "=" * 80)
    print("DATA GENERATION COMPLETE")
    print("=" * 80)
    print(f"\nData Summary:")
    print(f"  Date range: {combined_orders['order_date'].min()} to {combined_orders['order_date'].max()}")
    print(f"  Total orders: {len(combined_orders):,}")
    print(f"  Total items: {len(combined_items):,}")
    print(f"  Total revenue: ₹{combined_orders['total_amount'].sum() / 100:,.2f}")
    print(f"\nNew data added:")
    print(f"  New orders: {len(new_orders):,}")
    print(f"  New items: {len(new_items):,}")
    print(f"  New revenue: ₹{new_orders_df['total_amount'].sum() / 100:,.2f}")
    print(f"\nNext step: Run import_to_mongodb.py to load into database")
    print("=" * 80)

if __name__ == "__main__":
    generate_extended_data()

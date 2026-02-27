#!/usr/bin/env python3
"""
Import delivery orders from CSV to MongoDB.

This script imports delivery order data (Zomato, Swiggy, Walk-in orders)
from a CSV file into the MongoDB delivery_orders collection.

Usage:
    python import_delivery_orders.py <csv_file> [restaurant_id]

CSV Format:
    Order_Date,Total_INR,Promo_Discount_INR,Item_Discount_INR,Tax_GST_INR,Delivery_Fee_INR,Packaging_Charge_INR,Order_Channel
    2024-01-15,450.00,50.00,25.00,38.00,30.00,10.00,Zomato

Arguments:
    csv_file: Path to CSV file with delivery order data
    restaurant_id: Optional restaurant identifier (default: 'default')
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from pymongo import MongoClient


def import_from_csv(csv_file: str, restaurant_id: str = 'default'):
    """Import delivery orders from CSV file"""

    # Validate file exists
    if not Path(csv_file).exists():
        print(f"ERROR: File not found: {csv_file}")
        return 1

    # Read CSV
    try:
        df = pd.read_csv(csv_file)
        print(f"Loaded {len(df)} rows from {csv_file}")
    except Exception as e:
        print(f"ERROR: Failed to read CSV: {e}")
        return 1

    # Validate required columns
    required_columns = [
        'Order_Date', 'Total_INR', 'Promo_Discount_INR',
        'Item_Discount_INR', 'Tax_GST_INR', 'Delivery_Fee_INR',
        'Packaging_Charge_INR', 'Order_Channel'
    ]

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        print(f"ERROR: Missing required columns: {', '.join(missing)}")
        return 1

    # Connect to database
    try:
        mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
        db_name = os.getenv('DB_NAME', 'ahar_pos')

        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        # Test connection
        client.server_info()
        db = client[db_name]
        collection = db.delivery_orders

        print(f"Connected to MongoDB database: {db_name}")
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        return 1

    # Convert DataFrame rows to documents
    order_docs = []
    now = datetime.utcnow()

    for idx, row in df.iterrows():
        try:
            # Parse date
            order_date = pd.to_datetime(row['Order_Date'])

            # Validate channel
            channel = row['Order_Channel']
            if channel not in ['Zomato', 'Swiggy', 'WalkIn']:
                print(f"WARNING: Invalid channel '{channel}' at row {idx+2}, skipping")
                continue

            order_doc = {
                'order_date': order_date.to_pydatetime(),
                'total_inr': float(row['Total_INR']),
                'promo_discount_inr': float(row.get('Promo_Discount_INR', 0)),
                'item_discount_inr': float(row.get('Item_Discount_INR', 0)),
                'tax_gst_inr': float(row.get('Tax_GST_INR', 0)),
                'delivery_fee_inr': float(row.get('Delivery_Fee_INR', 0)),
                'packaging_charge_inr': float(row.get('Packaging_Charge_INR', 0)),
                'order_channel': channel,
                'restaurant_id': restaurant_id,
                'created_at': now,
                'updated_at': None
            }
            order_docs.append(order_doc)

        except Exception as e:
            print(f"WARNING: Failed to parse row {idx+2}: {e}")
            continue

    if not order_docs:
        print("ERROR: No valid orders to import")
        return 1

    print(f"Parsed {len(order_docs)} valid orders")

    # Bulk insert
    try:
        result = collection.insert_many(order_docs, ordered=False)
        inserted_count = len(result.inserted_ids)
        print(f"SUCCESS: Imported {inserted_count} delivery orders to MongoDB")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to import orders: {e}")
        return 1


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python import_delivery_orders.py <csv_file> [restaurant_id]")
        print("\nCSV Format:")
        print("  Order_Date,Total_INR,Promo_Discount_INR,Item_Discount_INR,")
        print("  Tax_GST_INR,Delivery_Fee_INR,Packaging_Charge_INR,Order_Channel")
        print("\nExample:")
        print("  python import_delivery_orders.py orders_jan2024.csv")
        print("  python import_delivery_orders.py orders_jan2024.csv my_restaurant")
        return 1

    csv_file = sys.argv[1]
    restaurant_id = sys.argv[2] if len(sys.argv) == 3 else 'default'

    return import_from_csv(csv_file, restaurant_id)


if __name__ == "__main__":
    sys.exit(main())

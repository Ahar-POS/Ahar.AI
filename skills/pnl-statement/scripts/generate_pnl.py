#!/usr/bin/env python3
"""
P&L Report Generator - Executes in Skills API container

This script generates a P&L Excel report from filtered order data.
Cost optimization: Script execution costs 0 tokens (only output is counted).

Usage:
    python generate_pnl.py <start_date> <end_date> <data_file>

Example:
    python generate_pnl.py 2024-01-01 2024-01-31 /data/orders.csv

Exit codes:
    0 - Success
    1 - Error (missing file, invalid data, etc.)
"""

import sys
import pandas as pd
from openpyxl import load_workbook
from pathlib import Path
from datetime import datetime


def load_and_validate_data(data_file: str) -> pd.DataFrame:
    """Load CSV and validate required columns exist"""

    required_columns = [
        'Order_Date', 'Total_INR', 'Promo_Discount_INR',
        'Item_Discount_INR', 'Tax_GST_INR', 'Delivery_Fee_INR',
        'Packaging_Charge_INR', 'Order_Channel'
    ]

    try:
        df = pd.read_csv(data_file)
    except FileNotFoundError:
        print(f"ERROR:Data file not found: {data_file}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR:Failed to read CSV: {e}")
        sys.exit(1)

    # Validate columns
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        print(f"ERROR:Missing required columns: {', '.join(missing)}")
        sys.exit(1)

    return df


def compute_pnl_metrics(df: pd.DataFrame) -> dict:
    """Compute all P&L metrics from order data"""

    # Revenue calculations
    gross_revenue = float(df['Total_INR'].sum())
    promo_discount = float(df['Promo_Discount_INR'].sum())
    item_discount = float(df['Item_Discount_INR'].sum())
    net_revenue = gross_revenue - promo_discount - item_discount

    # Cost calculations
    tax = float(df['Tax_GST_INR'].sum())
    delivery = float(df['Delivery_Fee_INR'].sum())
    packaging = float(df['Packaging_Charge_INR'].sum())

    # COGS estimation (35% of net revenue)
    # TODO: Replace with actual COGS when order_line_items data is integrated
    cogs = net_revenue * 0.35

    total_costs = tax + delivery + packaging + cogs

    # Net profit
    net_profit = net_revenue - total_costs

    # Channel breakdown
    channel_revenue = df.groupby('Order_Channel')['Total_INR'].sum().to_dict()

    return {
        'gross_revenue': gross_revenue,
        'promo_discount': promo_discount,
        'item_discount': item_discount,
        'net_revenue': net_revenue,
        'tax': tax,
        'delivery': delivery,
        'packaging': packaging,
        'cogs': cogs,
        'total_costs': total_costs,
        'net_profit': net_profit,
        'channel_revenue': channel_revenue
    }


def fill_template(metrics: dict, start_date: str, end_date: str) -> str:
    """Fill P&L template with computed metrics"""

    # Template path in container
    template_path = '/skills/pnl-statement/assets/pnl_template.xlsx'

    if not Path(template_path).exists():
        print(f"ERROR:Template not found: {template_path}")
        sys.exit(1)

    try:
        # Load template
        wb = load_workbook(template_path)
        ws = wb['P&L']

        # Fill header with date range
        ws['B2'] = f"Period: {start_date} to {end_date}"

        # Fill revenue section (rows 5-8)
        ws['B5'] = metrics['gross_revenue']
        ws['B6'] = metrics['promo_discount']
        ws['B7'] = metrics['item_discount']
        ws['B8'] = metrics['net_revenue']

        # Fill costs section (rows 11-15)
        ws['B11'] = metrics['tax']
        ws['B12'] = metrics['delivery']
        ws['B13'] = metrics['packaging']
        ws['B14'] = metrics['cogs']
        ws['B15'] = metrics['total_costs']

        # Fill net profit (row 17)
        ws['B17'] = metrics['net_profit']

        # Fill channel breakdown (starting row 20)
        row = 20
        for channel, amount in sorted(metrics['channel_revenue'].items()):
            ws[f'A{row}'] = channel
            ws[f'B{row}'] = amount
            row += 1

        # Save output
        output_dir = Path('/output')
        output_dir.mkdir(exist_ok=True)

        output_file = output_dir / f'pnl_report_{start_date}_{end_date}.xlsx'
        wb.save(output_file)

        return str(output_file)

    except Exception as e:
        print(f"ERROR:Failed to generate report: {e}")
        sys.exit(1)


def generate_pnl(start_date: str, end_date: str, data_file: str):
    """Main function to generate P&L report"""

    # Load and validate data
    df = load_and_validate_data(data_file)

    # Compute metrics
    metrics = compute_pnl_metrics(df)

    # Fill template and save
    output_file = fill_template(metrics, start_date, end_date)

    # Success message (Claude reads this)
    print(f"SUCCESS:{output_file}")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("ERROR:Usage: python generate_pnl.py <start_date> <end_date> <data_file>")
        sys.exit(1)

    start_date = sys.argv[1]
    end_date = sys.argv[2]
    data_file = sys.argv[3]

    sys.exit(generate_pnl(start_date, end_date, data_file))

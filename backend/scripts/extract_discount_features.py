"""
Extract Discount Features from Orders Data

This script analyzes discount patterns from the Lexis orders data and creates
daily discount features for demand forecasting.

Usage:
    python scripts/extract_discount_features.py --lexis-file /path/to/orders.xlsx
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime
import argparse

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


def load_and_analyze_discounts(file_path: str) -> pd.DataFrame:
    """
    Load orders data and extract discount information

    Expected columns in Lexis data:
    - Date/Order Date
    - Qty/Quantity
    - Price/Amount
    - Discount/Discount Amount (if present)
    - Total/Net Amount
    """
    print(f"Loading orders data from: {file_path}")

    # Try different header rows (Lexis exports vary)
    for header_row in [4, 5, 6, 0]:
        try:
            df = pd.read_excel(file_path, header=header_row)

            # Find date column
            date_cols = [col for col in df.columns if 'date' in str(col).lower()]
            if not date_cols:
                continue

            date_col = date_cols[0]
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df = df[df[date_col].notna()]

            if len(df) > 0:
                print(f"✓ Loaded {len(df):,} order line items")
                print(f"  Date column: {date_col}")
                print(f"  Available columns: {list(df.columns)}")
                print(f"  Date range: {df[date_col].min().date()} to {df[date_col].max().date()}")

                # Rename date column for consistency
                df = df.rename(columns={date_col: 'date'})
                return df

        except Exception as e:
            continue

    raise ValueError("Could not load orders data - check file format")


def extract_discount_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract discount-related features from order-level data

    Features created:
    1. Daily discount statistics (count, total, average)
    2. Discount penetration (% of orders with discount)
    3. Discount intensity (avg discount % when present)
    4. Day-of-week discount patterns
    """

    # Find discount-related columns
    discount_cols = [col for col in df.columns if 'discount' in str(col).lower()]
    price_cols = [col for col in df.columns if any(x in str(col).lower() for x in ['price', 'amount', 'total'])]
    qty_cols = [col for col in df.columns if 'qty' in str(col).lower() or 'quantity' in str(col).lower()]

    print(f"\nFound columns:")
    print(f"  Discount columns: {discount_cols}")
    print(f"  Price columns: {price_cols}")
    print(f"  Quantity columns: {qty_cols}")

    # Try to identify the discount column
    if len(discount_cols) == 0:
        print("\n⚠️  WARNING: No discount column found!")
        print("  Trying to calculate from price difference...")

        # Try to infer discount from price columns
        # Common patterns: Total - Subtotal = Discount
        # Or: (Price * Qty) - Total = Discount

        if len(price_cols) >= 2:
            # Assume first is gross, second is net
            df['discount_amount'] = df[price_cols[0]] - df[price_cols[1]]
            df['discount_amount'] = df['discount_amount'].clip(lower=0)  # Only positive discounts
        else:
            print("  Cannot infer discount - will create placeholder features")
            df['discount_amount'] = 0
    else:
        # Use the discount column
        discount_col = discount_cols[0]
        df['discount_amount'] = pd.to_numeric(df[discount_col], errors='coerce').fillna(0)

    # Get price for discount percentage calculation
    if len(price_cols) > 0:
        # Use gross price (before discount)
        price_col = price_cols[0]
        df['gross_price'] = pd.to_numeric(df[price_col], errors='coerce').fillna(0)

        # Calculate discount percentage
        df['discount_pct'] = np.where(
            df['gross_price'] > 0,
            (df['discount_amount'] / df['gross_price']) * 100,
            0
        )
    else:
        df['discount_pct'] = 0

    # Get quantity
    if len(qty_cols) > 0:
        qty_col = qty_cols[0]
        df['qty'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(1)
    else:
        df['qty'] = 1

    # Create binary discount flag
    df['has_discount'] = (df['discount_amount'] > 0).astype(int)

    print(f"\nDiscount Statistics:")
    print(f"  Total orders: {len(df):,}")
    print(f"  Orders with discount: {df['has_discount'].sum():,} ({df['has_discount'].mean()*100:.1f}%)")
    print(f"  Total discount amount: ₹{df['discount_amount'].sum():,.0f}")
    print(f"  Avg discount when present: ₹{df[df['has_discount']==1]['discount_amount'].mean():.2f}")
    print(f"  Avg discount %: {df[df['has_discount']==1]['discount_pct'].mean():.1f}%")
    print(f"  Max discount: ₹{df['discount_amount'].max():.2f}")

    return df


def create_daily_discount_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate order-level discounts to daily features

    Daily features:
    - discount_order_count: Number of discounted orders
    - discount_total_amount: Total discount given
    - discount_penetration: % of orders with discount
    - discount_avg_pct: Average discount percentage
    - discount_intensity: High/medium/low discount day
    """

    # Aggregate by date
    daily_discount = df.groupby('date').agg({
        'has_discount': ['sum', 'mean'],  # Count and penetration
        'discount_amount': ['sum', 'mean'],  # Total and average
        'discount_pct': 'mean',  # Average percentage
        'qty': 'sum'  # Total items (for normalization)
    }).reset_index()

    # Flatten column names
    daily_discount.columns = [
        'ds',
        'discount_order_count',
        'discount_penetration',
        'discount_total_amount',
        'discount_avg_amount',
        'discount_avg_pct',
        'total_items'
    ]

    # Create discount intensity categories
    # High: >30% of orders discounted or avg discount >15%
    # Medium: 10-30% penetration or 5-15% avg discount
    # Low: <10% penetration or <5% avg discount

    daily_discount['discount_intensity'] = 'none'
    daily_discount.loc[
        (daily_discount['discount_penetration'] > 0.3) |
        (daily_discount['discount_avg_pct'] > 15),
        'discount_intensity'
    ] = 'high'

    daily_discount.loc[
        ((daily_discount['discount_penetration'] > 0.1) & (daily_discount['discount_penetration'] <= 0.3)) |
        ((daily_discount['discount_avg_pct'] > 5) & (daily_discount['discount_avg_pct'] <= 15)),
        'discount_intensity'
    ] = 'medium'

    daily_discount.loc[
        (daily_discount['discount_penetration'] > 0) & (daily_discount['discount_penetration'] <= 0.1) &
        (daily_discount['discount_avg_pct'] <= 5),
        'discount_intensity'
    ] = 'low'

    # Binary flags for model
    daily_discount['is_high_discount_day'] = (daily_discount['discount_intensity'] == 'high').astype(int)
    daily_discount['is_medium_discount_day'] = (daily_discount['discount_intensity'] == 'medium').astype(int)
    daily_discount['has_any_discount'] = (daily_discount['discount_penetration'] > 0).astype(int)

    # Add day of week for pattern analysis
    daily_discount['day_of_week'] = pd.to_datetime(daily_discount['ds']).dt.dayofweek
    daily_discount['day_name'] = pd.to_datetime(daily_discount['ds']).dt.day_name()

    print(f"\n{'='*80}")
    print("DAILY DISCOUNT FEATURES")
    print(f"{'='*80}\n")

    print(f"Total days: {len(daily_discount)}")
    print(f"Days with any discount: {daily_discount['has_any_discount'].sum()}")
    print(f"High discount days: {daily_discount['is_high_discount_day'].sum()}")
    print(f"Medium discount days: {daily_discount['is_medium_discount_day'].sum()}")
    print(f"Low discount days: {(daily_discount['discount_intensity'] == 'low').sum()}")

    # Day of week analysis
    print(f"\nDiscount Penetration by Day of Week:")
    dow_discount = daily_discount.groupby('day_name')['discount_penetration'].mean() * 100
    for day, pct in dow_discount.items():
        print(f"  {day:10s}: {pct:5.1f}%")

    # Show top discount days
    print(f"\nTop 10 Discount Days:")
    top_days = daily_discount.nlargest(10, 'discount_total_amount')[
        ['ds', 'day_name', 'discount_total_amount', 'discount_penetration', 'discount_avg_pct']
    ]
    for _, row in top_days.iterrows():
        print(f"  {row['ds'].strftime('%Y-%m-%d')} ({row['day_name'][:3]}): "
              f"₹{row['discount_total_amount']:,.0f} | "
              f"{row['discount_penetration']*100:.1f}% orders | "
              f"{row['discount_avg_pct']:.1f}% avg")

    return daily_discount


def main():
    parser = argparse.ArgumentParser(description='Extract discount features from orders')
    parser.add_argument(
        '--lexis-file',
        type=str,
        default='/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx',
        help='Path to Lexis orders file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='/Users/pandiarajan/Ahar.AI/data/daily_discount_features.csv',
        help='Output path for daily discount features'
    )

    args = parser.parse_args()

    print("="*80)
    print("DISCOUNT FEATURE EXTRACTION")
    print("="*80)

    # Load orders
    df = load_and_analyze_discounts(args.lexis_file)

    # Extract discounts
    df = extract_discount_features(df)

    # Create daily features
    daily_discount = create_daily_discount_features(df)

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    daily_discount.to_csv(output_path, index=False)

    print(f"\n✓ Saved daily discount features to: {output_path}")

    print("\nFeatures created:")
    feature_cols = [
        'discount_order_count',
        'discount_penetration',
        'discount_total_amount',
        'discount_avg_pct',
        'is_high_discount_day',
        'is_medium_discount_day',
        'has_any_discount'
    ]
    for col in feature_cols:
        print(f"  - {col}")

    print("\nNext steps:")
    print("1. Features will be automatically loaded in ensemble_backtest.py")
    print("2. Run: python scripts/ensemble_backtest.py --model xgb_only --rolling-backtest")
    print("3. Check if discount features improve MAPE")


if __name__ == "__main__":
    main()

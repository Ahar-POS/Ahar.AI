"""
Validate generated test data for schema compliance, business logic, and ML patterns
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple
from scipy import stats
import sys

# ============================================================================
# VALIDATION CLASSES
# ============================================================================

class ValidationResult:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []

    def add_error(self, message: str):
        self.errors.append(f"❌ ERROR: {message}")

    def add_warning(self, message: str):
        self.warnings.append(f"⚠️  WARNING: {message}")

    def add_pass(self, message: str):
        self.passed.append(f"✓ {message}")

    def print_summary(self):
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)

        if self.passed:
            print(f"\n✅ PASSED ({len(self.passed)} checks)")
            for msg in self.passed:
                print(f"  {msg}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)})")
            for msg in self.warnings:
                print(f"  {msg}")

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)})")
            for msg in self.errors:
                print(f"  {msg}")

        print("\n" + "=" * 80)
        if not self.errors:
            print("✅ ALL VALIDATION CHECKS PASSED!")
        else:
            print(f"❌ VALIDATION FAILED: {len(self.errors)} error(s) found")
        print("=" * 80)

        return len(self.errors) == 0

# ============================================================================
# SCHEMA VALIDATION
# ============================================================================

def validate_schema(result: ValidationResult):
    """Validate data schema and required fields"""
    print("\n📋 Validating Schema Compliance...")

    # Load data
    try:
        orders = pd.read_csv('orders.csv')
        order_items = pd.read_csv('order_line_items.csv')
        promotions = pd.read_csv('promotions.csv')
        purchases = pd.read_csv('purchase_history.csv')
        wastage = pd.read_csv('wastage_log.csv')
        stockouts = pd.read_csv('stockout_log.csv')
    except FileNotFoundError as e:
        result.add_error(f"Missing file: {e}")
        return

    # Check orders schema
    required_order_fields = [
        'order_id', 'order_number', 'order_date', 'order_time', 'order_hour',
        'order_weekday', 'is_weekend', 'is_holiday', 'order_type', 'status',
        'total_amount', 'created_at'
    ]
    for field in required_order_fields:
        if field not in orders.columns:
            result.add_error(f"Orders missing required field: {field}")
        else:
            result.add_pass(f"Orders has field: {field}")

    # Check order items schema
    required_item_fields = [
        'order_item_id', 'order_id', 'menu_item_id', 'menu_item_name',
        'quantity', 'price_snapshot', 'item_status', 'created_at'
    ]
    for field in required_item_fields:
        if field not in order_items.columns:
            result.add_error(f"Order items missing required field: {field}")
        else:
            result.add_pass(f"Order items has field: {field}")

    # Check promotions schema
    required_promo_fields = [
        'promo_id', 'start_date', 'end_date', 'promo_type',
        'menu_item_ids', 'discount_pct', 'description'
    ]
    for field in required_promo_fields:
        if field not in promotions.columns:
            result.add_error(f"Promotions missing required field: {field}")
        else:
            result.add_pass(f"Promotions has field: {field}")

    # Check data types
    if not pd.api.types.is_integer_dtype(orders['total_amount']):
        result.add_error("Orders total_amount should be integer (paise)")
    else:
        result.add_pass("Orders total_amount is integer type")

    if not pd.api.types.is_integer_dtype(order_items['quantity']):
        result.add_error("Order items quantity should be integer")
    else:
        result.add_pass("Order items quantity is integer type")

    # Check for nulls in critical fields
    if orders['order_id'].isnull().any():
        result.add_error("Orders has null order_id values")
    else:
        result.add_pass("Orders has no null order_id values")

    if orders['total_amount'].isnull().any():
        result.add_error("Orders has null total_amount values")
    else:
        result.add_pass("Orders has no null total_amount values")

# ============================================================================
# BUSINESS LOGIC VALIDATION
# ============================================================================

def validate_business_logic(result: ValidationResult):
    """Validate business logic constraints"""
    print("\n💼 Validating Business Logic...")

    orders = pd.read_csv('orders.csv')
    order_items = pd.read_csv('order_line_items.csv')
    promotions = pd.read_csv('promotions.csv')

    # Check order amounts match item totals
    print("  Checking order amount calculations...")
    mismatches = 0
    for _, order in orders.iterrows():
        order_id = order['order_id']
        items = order_items[order_items['order_id'] == order_id]
        calculated_total = (items['price_snapshot'] * items['quantity']).sum()

        # Allow some tolerance for rounding and modifiers
        if abs(order['total_amount'] - calculated_total) > calculated_total * 0.25:
            mismatches += 1

    if mismatches > len(orders) * 0.05:  # More than 5% mismatches
        result.add_warning(f"Order amount mismatches: {mismatches} out of {len(orders)} orders")
    else:
        result.add_pass(f"Order amounts match item totals (within tolerance)")

    # Check foreign keys
    print("  Checking foreign key integrity...")
    orphaned_items = 0
    for _, item in order_items.iterrows():
        if item['order_id'] not in orders['order_id'].values:
            orphaned_items += 1

    if orphaned_items > 0:
        result.add_error(f"Found {orphaned_items} orphaned order items")
    else:
        result.add_pass("No orphaned order items")

    # Check promotion date ranges
    print("  Checking promotion date ranges...")
    for _, promo in promotions.iterrows():
        start = datetime.strptime(promo['start_date'], '%Y-%m-%d')
        end = datetime.strptime(promo['end_date'], '%Y-%m-%d')
        if end < start:
            result.add_error(f"Promotion {promo['promo_id']} has end_date before start_date")

    result.add_pass("Promotion date ranges are valid")

    # Check order status distribution
    print("  Checking order status distribution...")
    completed_pct = (orders['status'] == 'COMPLETED').sum() / len(orders) * 100
    if completed_pct < 85 or completed_pct > 98:
        result.add_warning(f"Completed orders: {completed_pct:.1f}% (expected 90-95%)")
    else:
        result.add_pass(f"Order completion rate: {completed_pct:.1f}%")

    # Check order types
    print("  Checking order type distribution...")
    order_types = orders['order_type'].value_counts(normalize=True) * 100
    if 'TAKEAWAY' not in order_types or order_types['TAKEAWAY'] < 60:
        result.add_warning(f"TAKEAWAY orders: {order_types.get('TAKEAWAY', 0):.1f}% (expected ~70%)")
    else:
        result.add_pass(f"Order type distribution looks realistic")

# ============================================================================
# PATTERN VALIDATION
# ============================================================================

def validate_patterns(result: ValidationResult):
    """Validate that data contains expected patterns for ML"""
    print("\n📊 Validating ML Patterns...")

    orders = pd.read_csv('orders.csv')
    promotions = pd.read_csv('promotions.csv')

    # Convert dates
    orders['order_date'] = pd.to_datetime(orders['order_date'])
    promotions['start_date'] = pd.to_datetime(promotions['start_date'])
    promotions['end_date'] = pd.to_datetime(promotions['end_date'])

    # Check daily order distribution
    print("  Checking daily order volume...")
    daily_orders = orders.groupby('order_date').size()
    mean_daily = daily_orders.mean()
    std_daily = daily_orders.std()
    min_daily = daily_orders.min()
    max_daily = daily_orders.max()

    print(f"    Mean: {mean_daily:.1f}, Std: {std_daily:.1f}, Min: {min_daily}, Max: {max_daily}")

    if mean_daily < 70 or mean_daily > 100:
        result.add_warning(f"Mean daily orders: {mean_daily:.1f} (expected 80-95)")
    else:
        result.add_pass(f"Daily order volume: {mean_daily:.1f} ± {std_daily:.1f}")

    # Check hourly distribution (bimodal)
    print("  Checking hourly distribution...")
    hour_dist = orders['order_hour'].value_counts(normalize=True).sort_index()
    peak_hours = hour_dist.nlargest(3).index.tolist()

    if 14 in peak_hours and (19 in peak_hours or 20 in peak_hours):
        result.add_pass(f"Bimodal distribution detected: peaks at hours {sorted(peak_hours)}")
    else:
        result.add_warning(f"Peak hours {sorted(peak_hours)} don't match expected bimodal pattern")

    # Check weekend pattern
    print("  Checking weekend pattern...")
    weekday_avg = orders[orders['is_weekend'] == False].groupby('order_date').size().mean()
    weekend_avg = orders[orders['is_weekend'] == True].groupby('order_date').size().mean()
    weekend_ratio = weekend_avg / weekday_avg

    print(f"    Weekday avg: {weekday_avg:.1f}, Weekend avg: {weekend_avg:.1f}, Ratio: {weekend_ratio:.2f}")

    if weekend_ratio < 0.75 or weekend_ratio > 0.95:
        result.add_warning(f"Weekend ratio: {weekend_ratio:.2f} (expected ~0.85)")
    else:
        result.add_pass(f"Weekend pattern detected: {weekend_ratio:.2f}x weekday volume")

    # Check holiday spikes
    print("  Checking holiday spikes...")
    if orders['is_holiday'].sum() > 0:
        holiday_avg = orders[orders['is_holiday'] == True].groupby('order_date').size().mean()
        regular_avg = orders[orders['is_holiday'] == False].groupby('order_date').size().mean()
        holiday_ratio = holiday_avg / regular_avg

        print(f"    Holiday avg: {holiday_avg:.1f}, Regular avg: {regular_avg:.1f}, Ratio: {holiday_ratio:.2f}")

        if holiday_ratio < 1.2:
            result.add_warning(f"Holiday boost: {holiday_ratio:.2f}x (expected >1.3x)")
        else:
            result.add_pass(f"Holiday spike detected: {holiday_ratio:.2f}x regular volume")

    # Check promotion impact
    print("  Checking promotion impact...")
    promo_dates = set()
    for _, promo in promotions.iterrows():
        date_range = pd.date_range(promo['start_date'], promo['end_date'])
        promo_dates.update(date_range)

    orders['has_promotion'] = orders['order_date'].isin(promo_dates)
    promo_avg = orders[orders['has_promotion']].groupby('order_date').size().mean()
    non_promo_avg = orders[~orders['has_promotion']].groupby('order_date').size().mean()

    if non_promo_avg > 0:
        promo_ratio = promo_avg / non_promo_avg
        print(f"    Promo avg: {promo_avg:.1f}, Non-promo avg: {non_promo_avg:.1f}, Ratio: {promo_ratio:.2f}")

        if promo_ratio < 1.1:
            result.add_warning(f"Promotion boost: {promo_ratio:.2f}x (expected >1.2x)")
        else:
            result.add_pass(f"Promotion impact detected: {promo_ratio:.2f}x baseline")

    # Check AOV distribution
    print("  Checking AOV distribution...")
    aov_mean = orders['total_amount'].mean() / 100  # Convert to rupees
    aov_std = orders['total_amount'].std() / 100

    print(f"    Mean AOV: ₹{aov_mean:.2f}, Std: ₹{aov_std:.2f}")

    if aov_mean < 600 or aov_mean > 1200:
        result.add_warning(f"Mean AOV: ₹{aov_mean:.2f} (expected ₹800-900)")
    else:
        result.add_pass(f"AOV distribution: ₹{aov_mean:.2f} ± ₹{aov_std:.2f}")

    # Check for growth trend
    print("  Checking growth trend...")
    orders_sorted = orders.sort_values('order_date')
    orders_sorted['day_num'] = (orders_sorted['order_date'] - orders_sorted['order_date'].min()).dt.days

    daily_counts = orders_sorted.groupby('day_num').size().reset_index(name='count')
    if len(daily_counts) > 10:
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            daily_counts['day_num'],
            daily_counts['count']
        )

        print(f"    Trend slope: {slope:.4f}, R²: {r_value**2:.4f}")

        if r_value**2 < 0.01:
            result.add_warning(f"No clear growth trend detected (R²={r_value**2:.4f})")
        else:
            result.add_pass(f"Growth trend detected: {slope:.4f} orders/day increase")

# ============================================================================
# DATA QUALITY CHECKS
# ============================================================================

def validate_data_quality(result: ValidationResult):
    """Check data quality metrics"""
    print("\n🔍 Validating Data Quality...")

    orders = pd.read_csv('orders.csv')
    order_items = pd.read_csv('order_line_items.csv')
    wastage = pd.read_csv('wastage_log.csv')
    stockouts = pd.read_csv('stockout_log.csv')

    # Check for duplicates
    print("  Checking for duplicates...")
    order_dupes = orders['order_id'].duplicated().sum()
    item_dupes = order_items['order_item_id'].duplicated().sum()

    if order_dupes > 0:
        result.add_error(f"Found {order_dupes} duplicate order IDs")
    else:
        result.add_pass("No duplicate order IDs")

    if item_dupes > 0:
        result.add_error(f"Found {item_dupes} duplicate order item IDs")
    else:
        result.add_pass("No duplicate order item IDs")

    # Check date range
    print("  Checking date range...")
    orders['order_date'] = pd.to_datetime(orders['order_date'])
    min_date = orders['order_date'].min()
    max_date = orders['order_date'].max()
    date_span = (max_date - min_date).days + 1

    print(f"    Date range: {min_date.date()} to {max_date.date()} ({date_span} days)")

    if date_span < 95 or date_span > 105:
        result.add_warning(f"Date span: {date_span} days (expected ~100)")
    else:
        result.add_pass(f"Date range: {date_span} days")

    # Check wastage records
    print("  Checking wastage data...")
    if len(wastage) < 500:
        result.add_warning(f"Wastage records: {len(wastage)} (expected >500)")
    else:
        result.add_pass(f"Wastage records: {len(wastage)}")

    # Check stock-outs
    print("  Checking stock-out data...")
    if len(stockouts) < 5 or len(stockouts) > 10:
        result.add_warning(f"Stock-out events: {len(stockouts)} (expected 6-8)")
    else:
        result.add_pass(f"Stock-out events: {len(stockouts)}")

    # Check items per order
    print("  Checking items per order...")
    items_per_order = order_items.groupby('order_id').size()
    mean_items = items_per_order.mean()

    print(f"    Mean items per order: {mean_items:.2f}")

    if mean_items < 1.5 or mean_items > 2.5:
        result.add_warning(f"Items per order: {mean_items:.2f} (expected ~1.7)")
    else:
        result.add_pass(f"Items per order: {mean_items:.2f}")

# ============================================================================
# MAIN VALIDATION
# ============================================================================

def main():
    """Run all validation checks"""
    print("=" * 80)
    print("DATA VALIDATION")
    print("=" * 80)

    result = ValidationResult()

    try:
        validate_schema(result)
        validate_business_logic(result)
        validate_patterns(result)
        validate_data_quality(result)
    except Exception as e:
        result.add_error(f"Validation failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()

    # Print summary
    success = result.print_summary()

    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()

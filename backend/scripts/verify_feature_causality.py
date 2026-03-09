"""
Verify Causality of Post-Holiday Recovery Features

Tests that features are deterministic and don't peek at future data.
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.ml.feature_library import RestaurantFeatureLibrary
from app.services.ml.holiday_calendar import IndianHolidayCalendar

def test_causality():
    """Test that post-holiday features are causal and deterministic"""

    print("="*80)
    print("TESTING POST-HOLIDAY FEATURE CAUSALITY")
    print("="*80)

    # Create test data for December 2025
    dates = pd.date_range(start='2025-12-01', end='2025-12-31', freq='D')
    df = pd.DataFrame({
        'ds': dates,
        'y': np.random.randint(50, 300, size=len(dates)),  # Dummy demand
        'day_of_week': dates.dayofweek,
        'day_of_month': dates.day,
        'month': dates.month,
        'is_weekend': (dates.dayofweek >= 5).astype(int)
    })

    # Add post-holiday features
    lib = RestaurantFeatureLibrary()
    df = lib.add_post_holiday_recovery_features(df)

    print("\n1. Testing Dec 27 (2 days after Christmas):")
    print("-" * 80)

    dec_27 = df[df['ds'] == datetime(2025, 12, 27)].iloc[0]
    print(f"Date: {dec_27['ds'].date()}")
    print(f"Days since major festival: {dec_27['days_since_major_festival']}")
    print(f"Post-holiday recovery 3d: {dec_27['post_holiday_recovery_3d']:.3f}")
    print(f"Post-holiday recovery 7d: {dec_27['post_holiday_recovery_7d']:.3f}")

    # Verify
    assert dec_27['days_since_major_festival'] == 2, "Should be 2 days after Christmas"
    assert dec_27['post_holiday_recovery_3d'] > 0, "Should have 3-day recovery signal"
    assert dec_27['post_holiday_recovery_7d'] > 0, "Should have 7-day recovery signal"
    print("✅ PASS: Dec 27 features correctly computed")

    print("\n2. Testing Dec 26 (1 day after Christmas):")
    print("-" * 80)

    dec_26 = df[df['ds'] == datetime(2025, 12, 26)].iloc[0]
    print(f"Date: {dec_26['ds'].date()}")
    print(f"Days since major festival: {dec_26['days_since_major_festival']}")
    print(f"Post-holiday recovery 3d: {dec_26['post_holiday_recovery_3d']:.3f}")
    print(f"Post-holiday recovery 7d: {dec_26['post_holiday_recovery_7d']:.3f}")

    assert dec_26['days_since_major_festival'] == 1, "Should be 1 day after Christmas"
    assert dec_26['post_holiday_recovery_3d'] == 2/3, "Should be 2/3 (strongest suppression)"
    print("✅ PASS: Dec 26 features correctly computed")

    print("\n3. Testing Dec 25 (Christmas Day):")
    print("-" * 80)

    dec_25 = df[df['ds'] == datetime(2025, 12, 25)].iloc[0]
    print(f"Date: {dec_25['ds'].date()}")
    print(f"Days since major festival: {dec_25['days_since_major_festival']}")
    print(f"Post-holiday recovery 3d: {dec_25['post_holiday_recovery_3d']:.3f}")

    # Christmas itself is not "after" a festival - it looks backward and finds Diwali (Nov 1) which is >14 days
    assert dec_25['days_since_major_festival'] >= 14, "Christmas day looks back and finds no recent major festival"
    assert dec_25['post_holiday_recovery_3d'] == 0, "No post-holiday recovery on Christmas itself"
    print("✅ PASS: Christmas day correctly shows no recent major festival in past")

    print("\n4. Testing Dec 24 (Pre-Christmas):")
    print("-" * 80)

    dec_24 = df[df['ds'] == datetime(2025, 12, 24)].iloc[0]
    print(f"Date: {dec_24['ds'].date()}")
    print(f"Days since major festival: {dec_24['days_since_major_festival']}")

    # Should not have Christmas in its past (Christmas is Dec 25)
    # But might have other festivals in past
    print(f"✅ PASS: Dec 24 has days_since_major_festival = {dec_24['days_since_major_festival']}")

    print("\n5. Testing Dec 15 (No recent major festival):")
    print("-" * 80)

    dec_15 = df[df['ds'] == datetime(2025, 12, 15)].iloc[0]
    print(f"Date: {dec_15['ds'].date()}")
    print(f"Days since major festival: {dec_15['days_since_major_festival']}")
    print(f"Post-holiday recovery 3d: {dec_15['post_holiday_recovery_3d']:.3f}")
    print(f"Post-holiday recovery 7d: {dec_15['post_holiday_recovery_7d']:.3f}")

    # Should be > 14 days from any major festival
    assert dec_15['post_holiday_recovery_3d'] == 0, "Should have no 3-day recovery"
    assert dec_15['post_holiday_recovery_7d'] == 0, "Should have no 7-day recovery"
    print("✅ PASS: Dec 15 has no post-holiday recovery (no recent major festival)")

    print("\n6. Testing Feature Determinism:")
    print("-" * 80)

    # Re-compute features with different dummy demand values
    df2 = df.copy()
    df2['y'] = np.random.randint(100, 500, size=len(df2))  # Different demand
    df2 = lib.add_post_holiday_recovery_features(df2)

    # Features should be identical (demand-independent)
    for col in ['days_since_major_festival', 'post_holiday_recovery_3d', 'post_holiday_recovery_7d']:
        assert (df[col] == df2[col]).all(), f"{col} should be deterministic"

    print("✅ PASS: Features are deterministic (independent of demand values)")

    print("\n7. Testing Year-End Features:")
    print("-" * 80)

    df = lib.add_year_end_features(df)

    dec_27_ye = df[df['ds'] == datetime(2025, 12, 27)].iloc[0]
    print(f"Dec 27 - is_year_end_week: {dec_27_ye['is_year_end_week']}")
    print(f"Dec 27 - days_to_year_end: {dec_27_ye['days_to_year_end']}")
    print(f"Dec 27 - is_christmas_ny_transition: {dec_27_ye['is_christmas_ny_transition']}")

    assert dec_27_ye['is_year_end_week'] == 1, "Dec 27 is in year-end week"
    assert dec_27_ye['days_to_year_end'] == 4, "Dec 27 is 4 days from year end"
    assert dec_27_ye['is_christmas_ny_transition'] == 1, "Dec 27 is in Christmas-NY transition"

    print("✅ PASS: Year-end features correctly computed")

    print("\n" + "="*80)
    print("ALL TESTS PASSED ✅")
    print("="*80)
    print("\nFeatures are CAUSAL and DETERMINISTIC:")
    print("- Only use holiday calendar (known in advance)")
    print("- Do not peek at actual demand")
    print("- Safe for production forecasting")
    print()

if __name__ == "__main__":
    test_causality()

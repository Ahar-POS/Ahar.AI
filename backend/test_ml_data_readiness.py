"""
Test ML Data Readiness

Verifies that the generated test data is suitable for ML model training.
Tests for patterns, variance, correlations, and feature quality.
"""

import sys
import os
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from scipy import stats
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from app.core.database import get_database
from app.services.feature_engineering import FeatureEngineeringService


class MLDataReadinessTest:
    """Test suite for ML data readiness"""

    def __init__(self):
        self.results = []
        self.plots_dir = Path(__file__).parent / 'ml_readiness_plots'
        self.plots_dir.mkdir(exist_ok=True)

    def log_result(self, test_name: str, passed: bool, message: str):
        """Log test result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({
            'test': test_name,
            'passed': passed,
            'message': message
        })
        print(f"{status}: {test_name}")
        print(f"  {message}")

    async def test_data_availability(self, db):
        """Test 1: Check if all collections have data"""
        print("\n" + "=" * 80)
        print("TEST 1: Data Availability")
        print("=" * 80)

        collections = {
            'orders': 8000,  # Expected minimum
            'promotions': 5,
            'wastage_log': 500,
            'stockout_log': 5,
        }

        all_passed = True
        for coll, min_count in collections.items():
            count = await db[coll].count_documents({})
            passed = count >= min_count
            all_passed = all_passed and passed

            self.log_result(
                f"{coll} availability",
                passed,
                f"Found {count:,} documents (expected ≥{min_count:,})"
            )

        return all_passed

    async def test_feature_extraction(self, feature_service):
        """Test 2: Feature engineering works without errors"""
        print("\n" + "=" * 80)
        print("TEST 2: Feature Extraction")
        print("=" * 80)

        try:
            df = await feature_service.build_ml_features(include_lags=True)

            if df.empty:
                self.log_result(
                    "Feature extraction",
                    False,
                    "Feature extraction returned empty dataframe"
                )
                return False

            self.log_result(
                "Feature extraction",
                True,
                f"Extracted {len(df)} rows with {len(df.columns)} features"
            )

            # Check for required feature columns
            required_features = [
                'hour_of_day', 'day_of_week', 'is_weekend', 'is_holiday',
                'is_promotion_active', 'temperature_avg', 'season'
            ]

            missing_features = [f for f in required_features if f not in df.columns]
            if missing_features:
                self.log_result(
                    "Required features",
                    False,
                    f"Missing features: {missing_features}"
                )
                return False

            self.log_result(
                "Required features",
                True,
                f"All {len(required_features)} required features present"
            )

            return True

        except Exception as e:
            self.log_result(
                "Feature extraction",
                False,
                f"Failed with error: {str(e)}"
            )
            import traceback
            traceback.print_exc()
            return False

    async def test_missing_values(self, feature_service):
        """Test 3: Check for missing values in critical columns"""
        print("\n" + "=" * 80)
        print("TEST 3: Missing Values")
        print("=" * 80)

        df = await feature_service.build_ml_features(include_lags=False)

        if df.empty:
            self.log_result("Missing values", False, "No data to check")
            return False

        critical_cols = [
            'order_date', 'total_amount', 'hour_of_day', 'day_of_week',
            'is_weekend', 'is_promotion_active'
        ]

        all_passed = True
        for col in critical_cols:
            if col in df.columns:
                missing_count = df[col].isnull().sum()
                passed = missing_count == 0
                all_passed = all_passed and passed

                self.log_result(
                    f"Missing values in {col}",
                    passed,
                    f"{missing_count} missing values"
                )

        return all_passed

    async def test_feature_variance(self, feature_service):
        """Test 4: Check that features have sufficient variance"""
        print("\n" + "=" * 80)
        print("TEST 4: Feature Variance")
        print("=" * 80)

        df = await feature_service.build_ml_features(include_lags=False)

        if df.empty:
            self.log_result("Feature variance", False, "No data to check")
            return False

        numeric_cols = df.select_dtypes(include=[np.number]).columns

        # Exclude features that are expected to have low variance in snapshot data
        exclude_cols = [
            'order_weekday', 'order_hour',  # These can be constant
            'days_of_stock_remaining',  # Snapshot inventory feature
            'stockout_risk_score',  # Snapshot inventory feature
            'wastage_rate_7day_avg'  # Snapshot inventory feature
        ]

        low_variance_features = []
        for col in numeric_cols:
            if col not in exclude_cols:
                std = df[col].std()
                if std < 0.01:  # Very low variance
                    low_variance_features.append(col)

        if low_variance_features:
            self.log_result(
                "Feature variance",
                False,
                f"Low variance features: {low_variance_features}"
            )
            return False

        self.log_result(
            "Feature variance",
            True,
            f"All {len(numeric_cols)} numeric features have sufficient variance"
        )
        return True

    async def test_promotion_impact(self, db):
        """Test 5: Verify promotion days have higher demand"""
        print("\n" + "=" * 80)
        print("TEST 5: Promotion Impact")
        print("=" * 80)

        # Load orders
        orders = await db.orders.find({'status': 'COMPLETED'}).to_list(length=None)
        orders_df = pd.DataFrame(orders)
        orders_df['order_date'] = pd.to_datetime(orders_df['order_date'])

        # Load promotions
        promotions = await db.promotions.find({}).to_list(length=None)
        if not promotions:
            self.log_result("Promotion impact", False, "No promotions found")
            return False

        promotions_df = pd.DataFrame(promotions)
        promotions_df['start_date'] = pd.to_datetime(promotions_df['start_date'])
        promotions_df['end_date'] = pd.to_datetime(promotions_df['end_date'])

        # Mark promotion dates
        promo_dates = set()
        for _, promo in promotions_df.iterrows():
            date_range = pd.date_range(promo['start_date'], promo['end_date'])
            promo_dates.update(date_range)

        orders_df['has_promotion'] = orders_df['order_date'].isin(promo_dates)

        # Aggregate daily
        daily_orders = orders_df.groupby(['order_date', 'has_promotion']).size().reset_index(name='order_count')

        promo_days = daily_orders[daily_orders['has_promotion']]
        non_promo_days = daily_orders[~daily_orders['has_promotion']]

        if promo_days.empty or non_promo_days.empty:
            self.log_result("Promotion impact", False, "Insufficient data for comparison")
            return False

        promo_mean = promo_days['order_count'].mean()
        non_promo_mean = non_promo_days['order_count'].mean()
        boost_ratio = promo_mean / non_promo_mean

        # Statistical test (t-test)
        t_stat, p_value = stats.ttest_ind(
            promo_days['order_count'],
            non_promo_days['order_count']
        )

        passed = boost_ratio > 1.15 and p_value < 0.05

        self.log_result(
            "Promotion impact",
            passed,
            f"Promo boost: {boost_ratio:.2f}x, p-value: {p_value:.4f}"
        )

        return passed

    async def test_weekend_pattern(self, db):
        """Test 6: Verify weekend pattern is visible"""
        print("\n" + "=" * 80)
        print("TEST 6: Weekend Pattern")
        print("=" * 80)

        orders = await db.orders.find({'status': 'COMPLETED'}).to_list(length=None)
        orders_df = pd.DataFrame(orders)
        orders_df['order_date'] = pd.to_datetime(orders_df['order_date'])

        # Aggregate daily
        daily_orders = orders_df.groupby(['order_date', 'is_weekend']).size().reset_index(name='order_count')

        weekday_avg = daily_orders[~daily_orders['is_weekend']]['order_count'].mean()
        weekend_avg = daily_orders[daily_orders['is_weekend']]['order_count'].mean()
        weekend_ratio = weekend_avg / weekday_avg

        # Statistical test
        t_stat, p_value = stats.ttest_ind(
            daily_orders[~daily_orders['is_weekend']]['order_count'],
            daily_orders[daily_orders['is_weekend']]['order_count']
        )

        passed = 0.70 < weekend_ratio < 0.95 and p_value < 0.05

        self.log_result(
            "Weekend pattern",
            passed,
            f"Weekend ratio: {weekend_ratio:.2f}x, p-value: {p_value:.4f}"
        )

        return passed

    async def test_bimodal_distribution(self, db):
        """Test 7: Verify bimodal time distribution"""
        print("\n" + "=" * 80)
        print("TEST 7: Bimodal Time Distribution")
        print("=" * 80)

        orders = await db.orders.find({'status': 'COMPLETED'}).to_list(length=None)
        orders_df = pd.DataFrame(orders)

        hour_dist = orders_df['order_hour'].value_counts(normalize=True).sort_index()
        peak_hours = hour_dist.nlargest(3).index.tolist()

        # Check for lunch and dinner peaks
        has_lunch_peak = 14 in peak_hours or 13 in peak_hours
        has_dinner_peak = 19 in peak_hours or 20 in peak_hours

        passed = has_lunch_peak and has_dinner_peak

        self.log_result(
            "Bimodal distribution",
            passed,
            f"Peak hours: {sorted(peak_hours)} (expected lunch ~14:00, dinner ~19-20:00)"
        )

        return passed

    async def generate_visualizations(self, feature_service, db):
        """Generate visualization plots"""
        print("\n" + "=" * 80)
        print("GENERATING VISUALIZATIONS")
        print("=" * 80)

        # Load data
        orders = await db.orders.find({'status': 'COMPLETED'}).to_list(length=None)
        orders_df = pd.DataFrame(orders)
        orders_df['order_date'] = pd.to_datetime(orders_df['order_date'])

        # Plot 1: Daily order volume over time
        daily_orders = orders_df.groupby('order_date').size()

        plt.figure(figsize=(12, 6))
        plt.plot(daily_orders.index, daily_orders.values, linewidth=2)
        plt.title('Daily Order Volume (100 Days)', fontsize=16)
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Orders', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plot_path = self.plots_dir / 'daily_orders.png'
        plt.savefig(plot_path, dpi=150)
        plt.close()
        print(f"✓ Saved: {plot_path}")

        # Plot 2: Hourly distribution
        hourly_dist = orders_df['order_hour'].value_counts().sort_index()

        plt.figure(figsize=(12, 6))
        plt.bar(hourly_dist.index, hourly_dist.values, color='steelblue')
        plt.title('Hourly Order Distribution (Bimodal Pattern)', fontsize=16)
        plt.xlabel('Hour of Day', fontsize=12)
        plt.ylabel('Number of Orders', fontsize=12)
        plt.xticks(range(11, 23))
        plt.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plot_path = self.plots_dir / 'hourly_distribution.png'
        plt.savefig(plot_path, dpi=150)
        plt.close()
        print(f"✓ Saved: {plot_path}")

        # Plot 3: Promotion impact
        promotions = await db.promotions.find({}).to_list(length=None)
        if promotions:
            promotions_df = pd.DataFrame(promotions)
            promotions_df['start_date'] = pd.to_datetime(promotions_df['start_date'])
            promotions_df['end_date'] = pd.to_datetime(promotions_df['end_date'])

            promo_dates = set()
            for _, promo in promotions_df.iterrows():
                date_range = pd.date_range(promo['start_date'], promo['end_date'])
                promo_dates.update(date_range)

            orders_df['has_promotion'] = orders_df['order_date'].isin(promo_dates)
            daily_with_promo = orders_df.groupby('order_date').agg({
                'order_id': 'count',
                'has_promotion': 'first'
            })

            plt.figure(figsize=(12, 6))
            colors = ['orange' if p else 'steelblue' for p in daily_with_promo['has_promotion']]
            plt.bar(daily_with_promo.index, daily_with_promo['order_id'], color=colors, alpha=0.7)
            plt.title('Promotion Impact on Daily Orders', fontsize=16)
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Orders', fontsize=12)
            plt.legend(['Regular Days', 'Promotion Days'])
            plt.grid(True, alpha=0.3, axis='y')
            plt.tight_layout()
            plot_path = self.plots_dir / 'promotion_impact.png'
            plt.savefig(plot_path, dpi=150)
            plt.close()
            print(f"✓ Saved: {plot_path}")

        # Plot 4: AOV distribution
        plt.figure(figsize=(12, 6))
        plt.hist(orders_df['total_amount'] / 100, bins=50, color='green', alpha=0.7, edgecolor='black')
        plt.title('Average Order Value (AOV) Distribution', fontsize=16)
        plt.xlabel('Order Value (₹)', fontsize=12)
        plt.ylabel('Frequency', fontsize=12)
        plt.axvline(orders_df['total_amount'].mean() / 100, color='red', linestyle='--', linewidth=2, label='Mean')
        plt.legend()
        plt.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plot_path = self.plots_dir / 'aov_distribution.png'
        plt.savefig(plot_path, dpi=150)
        plt.close()
        print(f"✓ Saved: {plot_path}")

        print(f"\n✓ All plots saved to: {self.plots_dir}")

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("ML DATA READINESS TEST SUMMARY")
        print("=" * 80)

        passed = [r for r in self.results if r['passed']]
        failed = [r for r in self.results if not r['passed']]

        print(f"\nTotal Tests: {len(self.results)}")
        print(f"Passed: {len(passed)} ✓")
        print(f"Failed: {len(failed)} ✗")

        if failed:
            print("\nFailed Tests:")
            for result in failed:
                print(f"  ✗ {result['test']}: {result['message']}")

        print("\n" + "=" * 80)
        if len(failed) == 0:
            print("✅ ALL TESTS PASSED - DATA IS ML-READY!")
        else:
            print(f"❌ {len(failed)} TEST(S) FAILED - REVIEW REQUIRED")
        print("=" * 80)

        return len(failed) == 0


async def main():
    """Main test execution"""
    print("=" * 80)
    print("ML DATA READINESS TEST")
    print("=" * 80)
    print()

    # Connect to database
    from app.core.database import connect_to_database, close_database_connection
    await connect_to_database()

    # Get database connection
    db = get_database()

    # Initialize test suite
    test_suite = MLDataReadinessTest()

    # Initialize feature engineering service
    feature_service = FeatureEngineeringService(db)

    # Run tests
    try:
        await test_suite.test_data_availability(db)
        await test_suite.test_feature_extraction(feature_service)
        await test_suite.test_missing_values(feature_service)
        await test_suite.test_feature_variance(feature_service)
        await test_suite.test_promotion_impact(db)
        await test_suite.test_weekend_pattern(db)
        await test_suite.test_bimodal_distribution(db)

        # Generate visualizations
        await test_suite.generate_visualizations(feature_service, db)

    except Exception as e:
        print(f"\n❌ Test suite failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    # Print summary
    success = test_suite.print_summary()

    # Close database connection
    await close_database_connection()

    return success


if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

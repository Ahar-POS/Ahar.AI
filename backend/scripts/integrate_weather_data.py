"""
Integrate Weather Data into Forecasting Pipeline

Usage:
    python scripts/integrate_weather_data.py --weather-file /path/to/gurgaon_weather_oct_dec_2025.xlsx
"""

import pandas as pd
import sys
from pathlib import Path
from datetime import datetime
import argparse

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


def load_weather_data(weather_file: str) -> pd.DataFrame:
    """
    Load weather data from Excel file

    Expected columns:
    - date (YYYY-MM-DD)
    - temp_max, temp_min, temp_avg
    - precipitation_mm
    - humidity_avg
    - wind_speed_kmh
    - weather_condition
    - is_rainy, is_heavy_rain, is_extreme_temp
    """
    print(f"Loading weather data from: {weather_file}")

    weather = pd.read_excel(weather_file, sheet_name='weather_data')

    # Remove any rows with NaN dates (notes/metadata)
    weather = weather[weather['date'].notna()].copy()

    # Convert date column
    weather['date'] = pd.to_datetime(weather['date'], errors='coerce')

    # Drop any rows that couldn't be converted to dates
    weather = weather[weather['date'].notna()].copy()

    # Validate required columns
    required_cols = [
        'date', 'temp_max', 'temp_min', 'temp_avg',
        'precipitation_mm', 'humidity_avg', 'wind_speed_kmh',
        'weather_condition', 'is_rainy', 'is_heavy_rain', 'is_extreme_temp'
    ]

    missing_cols = set(required_cols) - set(weather.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Validate date range
    min_date = weather['date'].min()
    max_date = weather['date'].max()
    expected_days = (max_date - min_date).days + 1
    actual_days = len(weather)

    print(f"✓ Date range: {min_date.date()} to {max_date.date()}")
    print(f"✓ Days present: {actual_days}/{expected_days}")

    if actual_days != expected_days:
        print(f"⚠️  WARNING: Missing {expected_days - actual_days} days!")

    # Check for nulls
    null_counts = weather[required_cols].isnull().sum()
    if null_counts.sum() > 0:
        print("⚠️  WARNING: Found null values:")
        print(null_counts[null_counts > 0])

    print(f"\nWeather Statistics:")
    print(f"  Temp range: {weather['temp_avg'].min():.1f}°C - {weather['temp_avg'].max():.1f}°C")
    print(f"  Rainy days: {weather['is_rainy'].sum()} ({weather['is_rainy'].mean()*100:.1f}%)")
    print(f"  Heavy rain days: {weather['is_heavy_rain'].sum()}")
    print(f"  Extreme temp days: {weather['is_extreme_temp'].sum()}")

    return weather


def merge_weather_with_demand(daily_df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge weather data with daily demand data

    Args:
        daily_df: DataFrame with 'ds' (date) column and demand
        weather_df: DataFrame with 'date' column and weather features

    Returns:
        Merged DataFrame with weather features
    """
    # Rename weather date column to match demand data
    weather_df = weather_df.rename(columns={'date': 'ds'})

    # Merge on date
    merged = daily_df.merge(weather_df, on='ds', how='left')

    # Check for missing weather data
    weather_cols = [
        'temp_avg', 'precipitation_mm', 'humidity_avg',
        'is_rainy', 'is_heavy_rain', 'is_extreme_temp'
    ]

    missing_weather = merged[weather_cols].isnull().any(axis=1).sum()
    if missing_weather > 0:
        print(f"⚠️  WARNING: {missing_weather} days missing weather data")
        print("Dates with missing weather:")
        print(merged[merged[weather_cols].isnull().any(axis=1)]['ds'])

    print(f"\n✓ Merged weather data: {len(merged)} days")
    return merged


def validate_weather_impact(merged_df: pd.DataFrame):
    """Print statistics on weather-demand correlation"""
    print("\n" + "="*80)
    print("WEATHER IMPACT ANALYSIS")
    print("="*80)

    # Rainy days vs normal days
    rainy_demand = merged_df[merged_df['is_rainy'] == 1]['y'].mean()
    normal_demand = merged_df[merged_df['is_rainy'] == 0]['y'].mean()
    rain_boost = ((rainy_demand - normal_demand) / normal_demand) * 100

    print(f"\nRainy Days Impact:")
    print(f"  Avg demand on rainy days: {rainy_demand:.1f}")
    print(f"  Avg demand on normal days: {normal_demand:.1f}")
    print(f"  Rain boost: {rain_boost:+.1f}%")

    # Extreme temperature days
    extreme_demand = merged_df[merged_df['is_extreme_temp'] == 1]['y'].mean()
    moderate_demand = merged_df[merged_df['is_extreme_temp'] == 0]['y'].mean()
    extreme_boost = ((extreme_demand - moderate_demand) / moderate_demand) * 100

    print(f"\nExtreme Temperature Impact:")
    print(f"  Avg demand on extreme temp days: {extreme_demand:.1f}")
    print(f"  Avg demand on moderate temp days: {moderate_demand:.1f}")
    print(f"  Extreme temp boost: {extreme_boost:+.1f}%")

    # Temperature correlation
    temp_corr = merged_df[['temp_avg', 'y']].corr().iloc[0, 1]
    rain_corr = merged_df[['precipitation_mm', 'y']].corr().iloc[0, 1]

    print(f"\nCorrelations with Demand:")
    print(f"  Temperature: {temp_corr:+.3f}")
    print(f"  Precipitation: {rain_corr:+.3f}")

    print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(description='Integrate weather data')
    parser.add_argument(
        '--weather-file',
        type=str,
        required=True,
        help='Path to weather Excel file'
    )
    parser.add_argument(
        '--lexis-file',
        type=str,
        default='/Users/pandiarajan/Ahar.AI/lexis_real_data/Item_Report_With_CustomerOrder_Details_2026_03_07_11_46_11.xlsx',
        help='Path to Lexis data file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output path for merged data (optional)'
    )

    args = parser.parse_args()

    print("="*80)
    print("WEATHER DATA INTEGRATION")
    print("="*80)

    # Load weather data
    weather_df = load_weather_data(args.weather_file)

    # Load demand data
    print(f"\nLoading demand data from: {args.lexis_file}")
    from scripts.ensemble_backtest import load_lexis_data
    daily_df = load_lexis_data(args.lexis_file)

    # Merge
    merged_df = merge_weather_with_demand(daily_df, weather_df)

    # Validate impact
    validate_weather_impact(merged_df)

    # Save if requested
    if args.output:
        merged_df.to_csv(args.output, index=False)
        print(f"\n✓ Saved merged data to: {args.output}")

    print("\n✓ Weather integration complete!")
    print("\nNext steps:")
    print("1. Weather features will now be automatically used in forecasting")
    print("2. Run: python scripts/ensemble_backtest.py --model xgb_only --rolling-backtest")
    print("3. Check feature importance to see weather impact")


if __name__ == "__main__":
    main()

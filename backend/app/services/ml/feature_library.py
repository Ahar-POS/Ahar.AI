"""
Generic Feature Library for Restaurant Demand Forecasting

Provides reusable features that work for:
- Cloud kitchens (delivery-focused)
- Dine-in restaurants
- Hybrid models
- Any location/type

All features are parameterized to avoid overfitting to specific restaurants.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class RestaurantFeatureLibrary:
    """
    Generic feature engineering for restaurant demand forecasting

    Features are designed to be:
    1. Restaurant-agnostic (work for any type)
    2. Location-agnostic (work in any city)
    3. Parameterized (adapt to specific characteristics)
    """

    @staticmethod
    def add_delivery_peak_features(df: pd.DataFrame, restaurant_type: str = "Cloud Kitchen") -> pd.DataFrame:
        """
        Delivery peak hour patterns

        Args:
            df: DataFrame with 'ds' (date), 'day_of_week', 'month'
            restaurant_type: "Cloud Kitchen", "Dine-in", "QSR", etc.

        Returns:
            DataFrame with delivery peak features
        """
        df = df.copy()

        if restaurant_type == "Cloud Kitchen":
            # Peak dinner delivery: 7-9pm (assume evening patterns even without hour data)
            # Use day_of_week as proxy
            df['is_dinner_delivery_day'] = 1  # All days have dinner (baseline)

            # Weekend evenings are PEAK for delivery
            df['is_weekend_evening'] = df['is_weekend'].astype(int)

            # Friday evenings start weekend surge
            df['is_friday'] = (df['day_of_week'] == 4).astype(int)

        elif restaurant_type == "Dine-in":
            # Both lunch and dinner matter
            df['is_dine_in_day'] = 1

        # Universal: proximity to weekend (Thu-Fri surge anticipation)
        df['weekend_proximity'] = (5 - df['day_of_week']).clip(0, 5)

        return df

    @staticmethod
    def add_weather_delivery_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Weather impact on delivery demand - UNIVERSAL

        Rain = people stay home = more delivery orders

        Args:
            df: DataFrame with weather columns (if available)

        Returns:
            DataFrame with weather-delivery interaction features
        """
        df = df.copy()

        # Check if weather columns exist
        has_weather = 'is_rainy' in df.columns or 'temp_avg' in df.columns

        if has_weather:
            if 'is_rainy' in df.columns:
                # Rain boosts delivery significantly
                df['rain_delivery_boost'] = df['is_rainy'].astype(int)

                # Rain on weekends = HUGE boost (families order in)
                if 'is_weekend' in df.columns:
                    df['weekend_rain_combo'] = (df['is_weekend'] & df['is_rainy']).astype(int)

            if 'temp_avg' in df.columns:
                # Extreme temperatures drive delivery
                df['extreme_temp_delivery'] = ((df['temp_avg'] > 35) | (df['temp_avg'] < 15)).astype(int)
        else:
            # Placeholder for when weather data is added later
            df['rain_delivery_boost'] = 0
            df['weekend_rain_combo'] = 0
            df['extreme_temp_delivery'] = 0

        return df

    @staticmethod
    def add_platform_promotion_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Delivery platform (Swiggy/Zomato) promotion patterns - UNIVERSAL

        Common promotion days across platforms:
        - First week of month (new user offers)
        - Weekends (discount campaigns)
        - Month-end (cashback offers)

        Args:
            df: DataFrame with date columns

        Returns:
            DataFrame with platform promotion features
        """
        df = df.copy()

        # First week promotions (1st-7th)
        df['is_first_week'] = (df['day_of_month'] <= 7).astype(int)

        # Month-end cashback (25th onwards)
        df['is_month_end_week'] = (df['day_of_month'] >= 25).astype(int)

        # Weekend discount campaigns (Fri-Sun)
        df['is_weekend_discount'] = (df['day_of_week'] >= 4).astype(int)

        # Payday week spending surge (1-8, 15-22)
        df['is_payday_week'] = (
            df['day_of_month'].isin(range(1, 9)) |
            df['day_of_month'].isin(range(15, 23))
        ).astype(int)

        return df

    @staticmethod
    def add_residential_patterns(df: pd.DataFrame, area_type: str = "Residential") -> pd.DataFrame:
        """
        Residential vs commercial area patterns

        Args:
            df: DataFrame with temporal features
            area_type: "Residential", "Commercial", "Mixed"

        Returns:
            DataFrame with area-specific features
        """
        df = df.copy()

        if area_type == "Residential":
            # Families order more on weekends
            df['family_weekend_boost'] = df['is_weekend'].astype(int)

            # Late dinners common in residential (assume evening orders)
            df['late_dinner_pattern'] = df['is_weekend'].astype(int)

            # Salary-driven spending in residential areas
            df['salary_week_boost'] = df['is_payday_week'] if 'is_payday_week' in df.columns else 0

        elif area_type == "Commercial":
            # Weekday lunch dominates commercial
            df['weekday_lunch_pattern'] = (~df['is_weekend']).astype(int)

            # Business days matter (not weekends/holidays)
            df['is_business_day'] = (~df['is_weekend']).astype(int)

        return df

    @staticmethod
    def add_festival_event_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Festival and event impact - UNIVERSAL

        Major festivals drive huge delivery spikes

        Args:
            df: DataFrame with date column

        Returns:
            DataFrame with festival/event features
        """
        df = df.copy()

        # Check if event columns exist
        if 'is_festival' in df.columns:
            df['festival_boost'] = df['is_festival'].astype(int)

            # Pre-festival surge (day before)
            df['pre_festival_day'] = df['is_festival'].shift(-1).fillna(0).astype(int)

            # Festival weekends are MASSIVE
            if 'is_weekend' in df.columns:
                df['festival_weekend_combo'] = (df['is_festival'] & df['is_weekend']).astype(int)

        if 'is_ipl_match' in df.columns:
            df['sports_event_boost'] = df['is_ipl_match'].astype(int)

        # Month-specific patterns (Diwali in Oct-Nov, Christmas in Dec)
        df['is_festival_season'] = df['month'].isin([10, 11, 12]).astype(int)

        return df

    @staticmethod
    def add_volatility_features(df: pd.DataFrame, target_col: str = 'y') -> pd.DataFrame:
        """
        Demand volatility and variance features

        High variance days need different predictions

        Args:
            df: DataFrame with target column
            target_col: Name of demand column

        Returns:
            DataFrame with volatility features
        """
        df = df.copy()

        # Coefficient of variation (normalized volatility)
        if 'rolling_std_7' in df.columns and 'rolling_mean_7' in df.columns:
            df['cv_7day'] = df['rolling_std_7'] / (df['rolling_mean_7'] + 1)

        if 'rolling_std_14' in df.columns and 'rolling_mean_14' in df.columns:
            df['cv_14day'] = df['rolling_std_14'] / (df['rolling_mean_14'] + 1)

        # Recent trend direction
        if 'lag_7' in df.columns:
            df['demand_trend'] = ((df['rolling_mean_7'] - df['lag_7']) / (df['lag_7'] + 1)).clip(-1, 1)

        # Demand acceleration (2nd derivative)
        if 'lag_1' in df.columns and 'lag_7' in df.columns:
            df['demand_acceleration'] = (df['lag_1'] - df['lag_7']) / 7

        return df

    @staticmethod
    def add_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Feature interactions - combinations that amplify effects

        Args:
            df: DataFrame with base features

        Returns:
            DataFrame with interaction features
        """
        df = df.copy()

        # Weekend + Payday = extra spending
        if 'is_weekend' in df.columns and 'is_payday_week' in df.columns:
            df['weekend_payday_combo'] = (df['is_weekend'] & df['is_payday_week']).astype(int)

        # First Friday of month (payday + weekend start)
        if 'is_friday' in df.columns and 'is_first_week' in df.columns:
            df['first_friday'] = (df['is_friday'] & df['is_first_week']).astype(int)

        # Month-end weekend (salary + weekend)
        if 'is_weekend' in df.columns and 'is_month_end_week' in df.columns:
            df['month_end_weekend'] = (df['is_weekend'] & df['is_month_end_week']).astype(int)

        return df

    @staticmethod
    def add_post_holiday_recovery_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add causal post-holiday recovery features

        CRITICAL: These features are DETERMINISTIC and CAUSAL.
        - Use only the holiday calendar (known in advance)
        - No peeking at actual demand
        - Safe for production forecasting

        Recovery pattern hypothesis:
        - Day 1 after major festival: 60-70% of normal demand
        - Day 2 after major festival: 70-80% of normal demand
        - Day 3 after major festival: 80-90% of normal demand
        - Days 4-7: Gradual recovery to 100%

        Args:
            df: DataFrame with 'ds' (datetime) and temporal features

        Returns:
            DataFrame with post-holiday recovery features
        """
        from app.services.ml.holiday_calendar import IndianHolidayCalendar

        df = df.copy()

        # Initialize features
        df['days_since_holiday'] = 0
        df['days_since_major_festival'] = 0
        df['post_holiday_recovery_3d'] = 0.0
        df['post_holiday_recovery_7d'] = 0.0
        df['is_post_holiday_weekend'] = 0

        # For each date, look backward to find last holiday
        for idx, row in df.iterrows():
            date_val = row['ds']

            # Check past 14 days for holidays
            days_since_any = 999
            days_since_major = 999

            for days_back in range(1, 15):
                past_date = date_val - pd.Timedelta(days=days_back)
                holiday = IndianHolidayCalendar.get_holiday(past_date)

                if holiday:
                    # Found a holiday
                    if days_since_any == 999:
                        days_since_any = days_back

                    # Check if major festival
                    if holiday['name'] in ['Diwali', 'Holi', 'Christmas', 'Eid al-Fitr', 'Eid al-Adha']:
                        if days_since_major == 999:
                            days_since_major = days_back
                            break  # Found closest major festival

            df.at[idx, 'days_since_holiday'] = min(days_since_any, 14)
            df.at[idx, 'days_since_major_festival'] = min(days_since_major, 14)

        # Calculate recovery curves
        # 3-day recovery: Strong suppression for 3 days after major festival
        df['post_holiday_recovery_3d'] = np.where(
            df['days_since_major_festival'] <= 3,
            (3 - df['days_since_major_festival']) / 3.0,  # 1.0 → 0.33 → 0
            0.0
        )

        # 7-day recovery: Gradual recovery over 7 days
        df['post_holiday_recovery_7d'] = np.where(
            df['days_since_major_festival'] <= 7,
            (7 - df['days_since_major_festival']) / 7.0,  # 1.0 → 0.14 → 0
            0.0
        )

        # Post-holiday weekend (weekend right after major festival)
        if 'is_weekend' in df.columns:
            df['is_post_holiday_weekend'] = (
                (df['days_since_major_festival'] >= 1) &
                (df['days_since_major_festival'] <= 4) &
                (df['is_weekend'] == 1)
            ).astype(int)

        return df

    @staticmethod
    def add_year_end_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add year-end specific features

        Year-end period (Dec 25-31) has unique patterns:
        - Post-Christmas recovery
        - New Year buildup
        - End-of-year business closures

        Args:
            df: DataFrame with temporal features

        Returns:
            DataFrame with year-end features
        """
        df = df.copy()

        # Last week of year (Dec 25-31)
        df['is_year_end_week'] = (
            (df['month'] == 12) & (df['day_of_month'] >= 25)
        ).astype(int)

        # Days until year end
        df['days_to_year_end'] = np.where(
            df['month'] == 12,
            31 - df['day_of_month'],
            0
        )

        # Days until month end (numeric version)
        df['days_to_month_end'] = df['ds'].dt.days_in_month - df['day_of_month']

        # Christmas to New Year transition period (Dec 26-30)
        df['is_christmas_ny_transition'] = (
            (df['month'] == 12) &
            (df['day_of_month'] >= 26) &
            (df['day_of_month'] <= 30)
        ).astype(int)

        return df


def build_cloud_kitchen_features(
    df: pd.DataFrame,
    restaurant_type: str = "Cloud Kitchen",
    area_type: str = "Residential",
    delivery_focused: bool = True
) -> pd.DataFrame:
    """
    Complete feature engineering pipeline for cloud kitchens

    Args:
        df: DataFrame with basic columns (ds, y, day_of_week, etc.)
        restaurant_type: Type of restaurant
        area_type: Type of area (Residential/Commercial)
        delivery_focused: Whether delivery is primary channel

    Returns:
        DataFrame with all engineered features
    """
    lib = RestaurantFeatureLibrary()

    # Add feature groups
    df = lib.add_delivery_peak_features(df, restaurant_type)
    df = lib.add_weather_delivery_features(df)
    df = lib.add_platform_promotion_features(df)
    df = lib.add_residential_patterns(df, area_type)
    df = lib.add_festival_event_features(df)
    df = lib.add_volatility_features(df)
    df = lib.add_interaction_features(df)

    # NEW: Post-holiday recovery features (causal, deterministic)
    df = lib.add_post_holiday_recovery_features(df)

    # NEW: Year-end calendar features (optional, for December-specific patterns)
    df = lib.add_year_end_features(df)

    return df

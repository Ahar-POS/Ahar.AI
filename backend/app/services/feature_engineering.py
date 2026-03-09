"""
Feature Engineering Service for ML Models

Extracts and engineers features from order and inventory data for demand forecasting
models (Prophet, SARIMA, XGBoost).
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class FeatureEngineeringService:
    """Service for feature engineering and extraction"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def load_orders_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Load orders from database"""
        query = {'status': 'COMPLETED'}

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter['$gte'] = start_date
            if end_date:
                date_filter['$lte'] = end_date
            query['order_date'] = date_filter

        orders = await self.db.orders.find(query).to_list(length=None)
        return pd.DataFrame(orders)

    async def load_promotions(self) -> pd.DataFrame:
        """Load promotions from database"""
        promotions = await self.db.promotions.find({}).to_list(length=None)
        if not promotions:
            return pd.DataFrame()
        return pd.DataFrame(promotions)

    async def load_wastage(self) -> pd.DataFrame:
        """Load wastage logs from database"""
        wastage = await self.db.wastage_log.find({}).to_list(length=None)
        if not wastage:
            return pd.DataFrame()
        return pd.DataFrame(wastage)

    async def load_inventory(self) -> pd.DataFrame:
        """Load current inventory from database"""
        inventory = await self.db.raw_material_inventory.find({}).to_list(length=None)
        return pd.DataFrame(inventory)

    def extract_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract temporal features from order data

        Features:
        - hour_of_day (0-23)
        - day_of_week (0-6, Monday=0)
        - day_of_month (1-31)
        - week_of_year (1-52)
        - month (1-12)
        - quarter (1-4)
        - is_weekend (boolean)
        - is_holiday (boolean)
        - days_until_next_holiday
        - season (winter/spring/summer/monsoon)
        """
        df = df.copy()

        # Ensure datetime
        df['order_date'] = pd.to_datetime(df['order_date'])

        # Basic temporal features
        df['hour_of_day'] = df['order_hour'] if 'order_hour' in df.columns else df['order_date'].dt.hour
        df['day_of_week'] = df['order_date'].dt.dayofweek
        df['day_of_month'] = df['order_date'].dt.day
        df['week_of_year'] = df['order_date'].dt.isocalendar().week
        df['month'] = df['order_date'].dt.month
        df['quarter'] = df['order_date'].dt.quarter

        # Weekend flag
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

        # Holiday flag (from existing column or default to False)
        if 'is_holiday' not in df.columns:
            df['is_holiday'] = False
        df['is_holiday'] = df['is_holiday'].astype(int)

        # Season (for India)
        df['season'] = df['month'].apply(self._get_season)

        # Days until next holiday (simplified - can be enhanced)
        df['days_until_next_holiday'] = df['order_date'].apply(self._days_to_next_holiday)

        return df

    def extract_lag_features(
        self,
        df: pd.DataFrame,
        target_col: str = 'total_amount',
        lags: List[int] = [1, 7, 30]
    ) -> pd.DataFrame:
        """
        Extract lag features for time series

        Features:
        - demand_lag_1 (yesterday)
        - demand_lag_7 (last week same day)
        - demand_lag_30 (last month same day)
        - demand_7day_rolling_mean
        - demand_7day_rolling_std
        - demand_30day_rolling_mean
        """
        df = df.copy()
        df = df.sort_values('order_date')

        # Aggregate daily
        daily_agg = df.groupby('order_date').agg({
            target_col: 'sum',
            'order_id': 'count'
        }).reset_index()
        daily_agg.columns = ['order_date', 'daily_revenue', 'daily_orders']

        # Lag features
        for lag in lags:
            daily_agg[f'revenue_lag_{lag}'] = daily_agg['daily_revenue'].shift(lag)
            daily_agg[f'orders_lag_{lag}'] = daily_agg['daily_orders'].shift(lag)

        # Rolling features
        daily_agg['revenue_7day_rolling_mean'] = daily_agg['daily_revenue'].rolling(window=7, min_periods=1).mean()
        daily_agg['revenue_7day_rolling_std'] = daily_agg['daily_revenue'].rolling(window=7, min_periods=1).std()
        daily_agg['revenue_30day_rolling_mean'] = daily_agg['daily_revenue'].rolling(window=30, min_periods=1).mean()
        daily_agg['orders_7day_rolling_mean'] = daily_agg['daily_orders'].rolling(window=7, min_periods=1).mean()

        # Merge back to original dataframe
        df = df.merge(daily_agg, on='order_date', how='left', suffixes=('', '_daily'))

        return df

    async def extract_promotion_features(
        self,
        df: pd.DataFrame,
        promotions: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Extract promotion-related features

        Features:
        - is_promotion_active (boolean)
        - promotion_discount_pct (0-100)
        - days_since_last_promotion
        - promotion_type (weekend/holiday/combo/none)
        """
        df = df.copy()

        if promotions is None or promotions.empty:
            # No promotions data
            df['is_promotion_active'] = False
            df['promotion_discount_pct'] = 0
            df['promotion_type'] = 'none'
            df['days_since_last_promotion'] = 999
            return df

        # Ensure datetime
        promotions['start_date'] = pd.to_datetime(promotions['start_date'])
        promotions['end_date'] = pd.to_datetime(promotions['end_date'])
        df['order_date'] = pd.to_datetime(df['order_date'])

        # For each order date, check if any promotion is active
        def get_promotion_info(date):
            active_promos = promotions[
                (promotions['start_date'] <= date) &
                (promotions['end_date'] >= date)
            ]

            if active_promos.empty:
                return False, 0, 'none'

            # If multiple promotions, take highest discount
            max_promo = active_promos.loc[active_promos['discount_pct'].idxmax()]
            return True, max_promo['discount_pct'], max_promo['promo_type']

        promo_info = df['order_date'].apply(get_promotion_info)
        df['is_promotion_active'] = promo_info.apply(lambda x: x[0]).astype(int)
        df['promotion_discount_pct'] = promo_info.apply(lambda x: x[1])
        df['promotion_type'] = promo_info.apply(lambda x: x[2])

        # Days since last promotion
        all_promo_dates = pd.concat([promotions['start_date'], promotions['end_date']]).unique()
        all_promo_dates = sorted(all_promo_dates)

        def days_since_promo(date):
            past_promos = [d for d in all_promo_dates if d <= date]
            if not past_promos:
                return 999
            return (date - max(past_promos)).days

        df['days_since_last_promotion'] = df['order_date'].apply(days_since_promo)

        return df

    async def extract_external_features(
        self,
        df: pd.DataFrame,
        mode: str = "training"
    ) -> pd.DataFrame:
        """
        Extract external features (weather, PyTrends, news, events)

        Two modes:
        1. "training": Use historical weather data (or synthetic if unavailable)
        2. "prediction": Use forecast weather data for future dates

        Features added:
        - Weather: temperature_avg, temp_min, temp_max, is_rainy, humidity, wind_speed
        - PyTrends: restaurant_search_trend, delivery_trend, cuisine_trend
        - News: food_trend_score (sentiment)
        - Events: is_festival, is_ipl_match, festival_impact_score

        Args:
            df: DataFrame with order_date column
            mode: "training" (historical) or "prediction" (forecast)

        Returns:
            DataFrame with external features added
        """
        from app.services.external_data import (
            get_weather_service,
            get_pytrends_service,
            get_news_service,
            get_events_service
        )

        df = df.copy()

        # Ensure datetime
        df['order_date'] = pd.to_datetime(df['order_date'])

        # ============================================================
        # WEATHER FEATURES
        # ============================================================
        weather_service = get_weather_service()

        if mode == "training":
            # Historical weather (for training models)
            # NOTE: Free OpenWeatherMap tier doesn't provide historical data
            # For production, consider paid tier or stored forecasts
            lookback_days = (df['order_date'].max() - df['order_date'].min()).days + 1
            historical_weather = await weather_service.get_historical_features(
                lookback_days=lookback_days
            )

            # Create date -> weather mapping
            weather_map = {w["date"]: w for w in historical_weather}

            # Map weather to dataframe dates
            def get_weather_for_date(date):
                date_str = date.strftime("%Y-%m-%d")
                return weather_map.get(date_str, {
                    "temp_avg": 25.0,
                    "temp_min": 20.0,
                    "temp_max": 30.0,
                    "is_rainy": False,
                    "humidity": 50.0,
                    "wind_speed": 10.0
                })

            weather_data = df['order_date'].apply(get_weather_for_date)

        else:  # mode == "prediction"
            # Forecast weather (for predictions)
            forecast_days = (df['order_date'].max() - df['order_date'].min()).days + 1
            forecast_weather = await weather_service.get_forecast_features(days=forecast_days)

            # Create date -> weather mapping
            weather_map = {w["date"]: w for w in forecast_weather}

            def get_weather_for_date(date):
                date_str = date.strftime("%Y-%m-%d")
                return weather_map.get(date_str, {
                    "temp_avg": 25.0,
                    "temp_min": 20.0,
                    "temp_max": 30.0,
                    "is_rainy": False,
                    "humidity": 50.0,
                    "wind_speed": 10.0
                })

            weather_data = df['order_date'].apply(get_weather_for_date)

        # Extract weather features
        df['temperature_avg'] = weather_data.apply(lambda x: x["temp_avg"])
        df['temperature_min'] = weather_data.apply(lambda x: x["temp_min"])
        df['temperature_max'] = weather_data.apply(lambda x: x["temp_max"])
        df['is_rainy'] = weather_data.apply(lambda x: int(x["is_rainy"]))
        df['humidity'] = weather_data.apply(lambda x: x["humidity"])
        df['wind_speed'] = weather_data.apply(lambda x: x["wind_speed"])

        # Weather condition (categorical)
        df['weather_condition'] = df['is_rainy'].apply(
            lambda x: 'rainy' if x else 'clear'
        )

        # ============================================================
        # PYTRENDS FEATURES (Critical for new cafes with <90 days data)
        # ============================================================
        pytrends_service = get_pytrends_service()

        if mode == "training":
            # TRAINING MODE: Use LAGGED trends (trends from previous day)
            # This avoids data leakage - only uses data available at prediction time

            # For each date, get trends from 1 day prior
            def get_lagged_trends(date):
                trends = pytrends_service.get_lagged_trends_for_date(
                    target_date=date,
                    lag_days=1,  # Use yesterday's trends
                    location="IN"
                )
                return trends

            trend_data = df['order_date'].apply(get_lagged_trends)

            # Extract trend features (now each row has different values!)
            df['restaurant_search_trend'] = trend_data.apply(lambda x: x["restaurant_search_trend"])
            df['delivery_trend'] = trend_data.apply(lambda x: x["delivery_trend"])
            df['dine_in_trend'] = trend_data.apply(lambda x: x["dine_in_trend"])
            df['cafe_trend'] = trend_data.apply(lambda x: x["cafe_trend"])

            # Simplified for lagged
            df['trend_direction'] = 'stable'
            df['weekly_trend_change_pct'] = 0.0

        else:  # mode == "prediction"
            # PREDICTION MODE: Use CURRENT/RECENT trends
            # These are available NOW for predicting FUTURE dates

            restaurant_trends = pytrends_service.get_restaurant_trends(
                location="IN",
                timeframe="today 3-m"
            )

            # Add trend features (same value for all future dates)
            df['restaurant_search_trend'] = restaurant_trends["restaurant_search_trend"]
            df['delivery_trend'] = restaurant_trends["delivery_trend"]
            df['dine_in_trend'] = restaurant_trends["dine_in_trend"]
            df['cafe_trend'] = restaurant_trends["cafe_trend"]
            df['trend_direction'] = restaurant_trends["trend_direction"]
            df['weekly_trend_change_pct'] = restaurant_trends["weekly_change_pct"]

        # ============================================================
        # NEWS SENTIMENT FEATURES
        # ============================================================
        news_service = get_news_service()

        if mode == "training":
            # TRAINING MODE: Use sentiment from week BEFORE each date
            # Note: NewsAPI free tier only allows last 30 days
            # For older dates, use rolling 7-day average or default

            # For simplicity in training, use a consistent neutral sentiment
            # Since news changes slowly, this is acceptable for MVP
            # TODO: Store daily news sentiment for better temporal alignment
            df['food_trend_score'] = 0.0  # Neutral
            df['news_sentiment'] = 'neutral'

            logger.info("Using neutral news sentiment for training (temporal alignment pending)")

        else:  # mode == "prediction"
            # PREDICTION MODE: Use CURRENT/RECENT sentiment
            news_sentiment = await news_service.get_food_trends_sentiment(
                country="in",
                lookback_days=7
            )

            # Add sentiment features
            df['food_trend_score'] = news_sentiment["food_trend_score"]
            df['news_sentiment'] = news_sentiment["sentiment"]

        # ============================================================
        # EVENT FEATURES
        # ============================================================
        events_service = get_events_service()

        # Get events for each date
        def get_event_features(date):
            return events_service.get_event_features_for_date(date)

        event_data = df['order_date'].apply(get_event_features)

        # Extract event features
        df['is_festival'] = event_data.apply(lambda x: int(x["is_festival"]))
        df['is_ipl_match'] = event_data.apply(lambda x: int(x["is_ipl_match"]))
        df['is_corporate_holiday'] = event_data.apply(lambda x: int(x["is_corporate_holiday"]))
        df['festival_impact_score'] = event_data.apply(lambda x: x["festival_impact_score"])
        df['total_event_impact'] = event_data.apply(lambda x: x["total_impact_score"])

        return df

    async def extract_inventory_features(
        self,
        df: pd.DataFrame,
        inventory: Optional[pd.DataFrame] = None,
        wastage: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Extract inventory-related features

        Features:
        - days_of_stock_remaining (avg across all materials)
        - stockout_risk_score (0-1)
        - wastage_rate_7day_avg
        """
        df = df.copy()

        if inventory is None or inventory.empty:
            df['days_of_stock_remaining'] = 30
            df['stockout_risk_score'] = 0.0
            df['wastage_rate_7day_avg'] = 0.0
            return df

        # Calculate average days of stock remaining
        inventory['days_of_stock'] = inventory.apply(
            lambda row: row['current_stock'] / max(row['reorder_qty'] / 7, 1),
            axis=1
        )
        avg_days_of_stock = inventory['days_of_stock'].mean()
        df['days_of_stock_remaining'] = avg_days_of_stock

        # Stock-out risk (if any material below reorder level)
        materials_at_risk = (inventory['current_stock'] < inventory['reorder_level']).sum()
        stockout_risk = min(materials_at_risk / len(inventory), 1.0)
        df['stockout_risk_score'] = stockout_risk

        # Wastage rate
        if wastage is not None and not wastage.empty:
            wastage['date'] = pd.to_datetime(wastage['date'])
            recent_wastage = wastage[wastage['date'] >= (datetime.now() - timedelta(days=7))]
            if not recent_wastage.empty:
                wastage_rate = recent_wastage['quantity_wasted'].sum() / max(recent_wastage['quantity_wasted'].count(), 1)
                df['wastage_rate_7day_avg'] = wastage_rate
            else:
                df['wastage_rate_7day_avg'] = 0.0
        else:
            df['wastage_rate_7day_avg'] = 0.0

        return df

    async def build_ml_features(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_lags: bool = True
    ) -> pd.DataFrame:
        """
        Build complete feature set for ML models

        Returns a dataframe with all engineered features ready for training/prediction
        """
        # Load data
        orders = await self.load_orders_data(start_date, end_date)

        if orders.empty:
            return pd.DataFrame()

        promotions = await self.load_promotions()
        wastage = await self.load_wastage()
        inventory = await self.load_inventory()

        # Extract features
        df = orders.copy()

        # Temporal features
        df = self.extract_temporal_features(df)

        # Lag features (if requested)
        if include_lags:
            df = self.extract_lag_features(df)

        # Promotion features
        df = await self.extract_promotion_features(df, promotions)

        # External features (real weather, PyTrends, news, events)
        df = await self.extract_external_features(df, mode="training")

        # Inventory features
        df = await self.extract_inventory_features(df, inventory, wastage)

        # Drop unnecessary columns for ML
        drop_cols = ['_id', 'table_id', 'staff_id', 'sent_to_kitchen_at', 'completed_at', 'holiday_name']
        for col in drop_cols:
            if col in df.columns:
                df = df.drop(columns=[col])

        return df

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    @staticmethod
    def _get_season(month: int) -> str:
        """Get season for given month (India)"""
        if month in [12, 1, 2]:
            return 'winter'
        elif month in [3, 4, 5]:
            return 'spring'
        elif month in [6, 7, 8, 9]:
            return 'monsoon'
        else:
            return 'autumn'

    @staticmethod
    def _days_to_next_holiday(date: datetime) -> int:
        """Calculate days until next holiday (simplified)"""
        # Indian holidays (simplified)
        holidays = [
            (1, 1),   # New Year
            (1, 14),  # Sankranti
            (1, 26),  # Republic Day
            (3, 8),   # Holi (approximate)
            (4, 14),  # Ambedkar Jayanti
            (8, 15),  # Independence Day
            (10, 2),  # Gandhi Jayanti
            (10, 24), # Diwali (approximate)
            (12, 25), # Christmas
        ]

        # Find next holiday
        current_date = (date.month, date.day)
        for holiday in holidays:
            if holiday > current_date:
                # Calculate days
                next_holiday_date = datetime(date.year, holiday[0], holiday[1])
                return (next_holiday_date - date).days

        # If no holiday found this year, return days to first holiday next year
        next_holiday_date = datetime(date.year + 1, holidays[0][0], holidays[0][1])
        return (next_holiday_date - date).days

    def get_feature_importance(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate basic feature importance using correlation with target

        Returns dictionary of feature names and their correlation with daily revenue
        """
        # Aggregate to daily level
        daily_df = df.groupby('order_date').agg({
            'total_amount': 'sum',
            'is_weekend': 'first',
            'is_holiday': 'first',
            'is_promotion_active': 'first',
            'promotion_discount_pct': 'first',
            'temperature_avg': 'mean',
            'is_rainy': 'first',
        }).reset_index()

        # Calculate correlations
        numeric_cols = daily_df.select_dtypes(include=[np.number]).columns
        correlations = {}

        for col in numeric_cols:
            if col != 'total_amount':
                corr = daily_df[col].corr(daily_df['total_amount'])
                if not np.isnan(corr):
                    correlations[col] = abs(corr)

        # Sort by importance
        return dict(sorted(correlations.items(), key=lambda x: x[1], reverse=True))

    async def get_daily_aggregates(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Get daily aggregated features for time series models

        Returns one row per day with:
        - daily_orders: Number of orders
        - daily_revenue: Total revenue
        - avg_order_value: Average order value
        - temporal features
        - promotion features
        - external features
        """
        df = await self.build_ml_features(start_date, end_date, include_lags=False)

        if df.empty:
            return pd.DataFrame()

        # Aggregate to daily level
        daily_df = df.groupby('order_date').agg({
            'order_id': 'count',
            'total_amount': ['sum', 'mean'],
            'is_weekend': 'first',
            'is_holiday': 'first',
            'day_of_week': 'first',
            'month': 'first',
            'quarter': 'first',
            'season': 'first',
            'is_promotion_active': 'max',
            'promotion_discount_pct': 'max',
            'temperature_avg': 'mean',
            'is_rainy': 'first',
            'weather_condition': lambda x: x.mode()[0] if len(x) > 0 else 'sunny',
        }).reset_index()

        # Flatten column names
        daily_df.columns = [
            'order_date', 'daily_orders', 'daily_revenue', 'avg_order_value',
            'is_weekend', 'is_holiday', 'day_of_week', 'month', 'quarter',
            'season', 'is_promotion_active', 'promotion_discount_pct',
            'temperature_avg', 'is_rainy', 'weather_condition'
        ]

        return daily_df

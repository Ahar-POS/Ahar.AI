"""
PyTrends Service for Google Trends Data

Critical for new cafes/QSRs with limited historical data (<90 days).
Provides market-level signals that help predict demand without requiring years of internal data.

Features:
- Restaurant search trends ("restaurant near me", "food delivery")
- Cuisine-specific trends ("sandwich cafe", "burger restaurant")
- Location-specific interest (city-level trends)
- Trend direction (this week vs last week)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pytrends.request import TrendReq
import time

logger = logging.getLogger(__name__)


class PyTrendsService:
    """
    Google Trends data service for demand forecasting

    Use cases:
    - New cafes (Tier 1-2): Heavy reliance on market trends (40-60% weight)
    - Established cafes (Tier 3-4): Supplementary signal (10-25% weight)

    Example:
    - "restaurant near me" searches up 25% → All restaurants benefit
    - "food delivery" searches trending → Delivery-focused cafes gain more
    - "Gurgaon cafe" searches spiking → Local demand surge
    """

    def __init__(self):
        self._pytrends = None
        self._cache: Dict[str, Any] = {}
        self._cache_ttl_hours = 24  # Cache trends for 24 hours

    def _get_pytrends(self) -> TrendReq:
        """Get or initialize PyTrends client"""
        if self._pytrends is None:
            self._pytrends = TrendReq(
                hl='en-IN',  # Hindi/English - India
                tz=330  # IST timezone offset (UTC+5:30)
            )
        return self._pytrends

    def get_restaurant_trends(
        self,
        location: str = "IN",  # India
        timeframe: str = "today 3-m",  # Last 3 months
        specific_date: Optional[datetime] = None  # For training: get trends for specific date
    ) -> Dict[str, Any]:
        """
        Get restaurant-related search trends

        Args:
            location: Country code (IN for India) or region
            timeframe: Timeframe for trends (e.g., "today 3-m", "today 1-m")

        Returns:
            {
                "restaurant_search_trend": 75,  # 0-100 normalized
                "delivery_trend": 65,
                "dine_in_trend": 45,
                "cafe_trend": 55,
                "trend_direction": "up",  # up/down/stable
                "weekly_change_pct": 12.5,
                "timestamp": "2026-03-08T10:00:00Z"
            }
        """
        cache_key = f"restaurant_trends_{location}_{timeframe}"

        # Check cache
        if self._is_cache_valid(cache_key):
            logger.info("Using cached restaurant trends")
            return self._cache[cache_key]

        try:
            pytrends = self._get_pytrends()

            # Keywords for restaurant demand
            keywords = [
                "restaurant near me",
                "food delivery",
                "dine in restaurant",
                "cafe near me"
            ]

            # Build payload
            pytrends.build_payload(
                kw_list=keywords,
                cat=0,  # All categories
                timeframe=timeframe,
                geo=location,
                gprop=''  # Web search
            )

            # Get interest over time
            interest_df = pytrends.interest_over_time()

            if interest_df.empty:
                logger.warning(f"No trends data for {location}")
                return self._get_default_trends()

            # Get latest values (most recent week)
            latest_values = interest_df.iloc[-1]

            # Calculate trend direction (compare last 2 weeks)
            if len(interest_df) >= 2:
                prev_values = interest_df.iloc[-2]
                avg_change = (
                    (latest_values[keywords].mean() - prev_values[keywords].mean())
                    / prev_values[keywords].mean() * 100
                )
            else:
                avg_change = 0

            # Determine trend direction
            if avg_change > 5:
                trend_direction = "up"
            elif avg_change < -5:
                trend_direction = "down"
            else:
                trend_direction = "stable"

            result = {
                "restaurant_search_trend": int(latest_values["restaurant near me"]),
                "delivery_trend": int(latest_values["food delivery"]),
                "dine_in_trend": int(latest_values["dine in restaurant"]),
                "cafe_trend": int(latest_values["cafe near me"]),
                "trend_direction": trend_direction,
                "weekly_change_pct": round(avg_change, 2),
                "timestamp": datetime.utcnow().isoformat()
            }

            # Cache the result
            self._cache[cache_key] = result
            self._cache[f"{cache_key}_time"] = datetime.utcnow()

            logger.info(f"Fetched restaurant trends: {result['trend_direction']} ({result['weekly_change_pct']}%)")
            return result

        except Exception as e:
            logger.error(f"PyTrends request failed: {e}")
            return self._get_default_trends()

    def get_cuisine_trends(
        self,
        cuisine_type: str,
        location: str = "IN",
        timeframe: str = "today 3-m"
    ) -> Dict[str, Any]:
        """
        Get trends for specific cuisine types

        Args:
            cuisine_type: Cuisine type (e.g., "sandwich", "burger", "pizza", "biryani")
            location: Country code or region
            timeframe: Timeframe for trends

        Returns:
            {
                "cuisine_trend": 45,  # 0-100 normalized
                "relative_interest": "rising",  # rising/falling/stable
                "trend_score": 0.65,  # Normalized 0-1
                "timestamp": "2026-03-08T10:00:00Z"
            }
        """
        cache_key = f"cuisine_trends_{cuisine_type}_{location}_{timeframe}"

        # Check cache
        if self._is_cache_valid(cache_key):
            logger.info(f"Using cached cuisine trends for {cuisine_type}")
            return self._cache[cache_key]

        try:
            pytrends = self._get_pytrends()

            # Build cuisine-specific keywords
            keywords = [
                f"{cuisine_type} restaurant",
                f"{cuisine_type} near me",
                f"best {cuisine_type}"
            ]

            # Build payload
            pytrends.build_payload(
                kw_list=keywords,
                cat=0,
                timeframe=timeframe,
                geo=location,
                gprop=''
            )

            # Get interest over time
            interest_df = pytrends.interest_over_time()

            if interest_df.empty:
                logger.warning(f"No trends data for {cuisine_type}")
                return self._get_default_cuisine_trends()

            # Average across keywords
            latest_avg = interest_df[keywords].iloc[-1].mean()

            # Calculate trend
            if len(interest_df) >= 2:
                prev_avg = interest_df[keywords].iloc[-2].mean()
                change_pct = (latest_avg - prev_avg) / prev_avg * 100
            else:
                change_pct = 0

            # Determine relative interest
            if change_pct > 10:
                relative_interest = "rising"
            elif change_pct < -10:
                relative_interest = "falling"
            else:
                relative_interest = "stable"

            result = {
                "cuisine_trend": int(latest_avg),
                "relative_interest": relative_interest,
                "trend_score": round(latest_avg / 100, 2),  # Normalize to 0-1
                "change_pct": round(change_pct, 2),
                "timestamp": datetime.utcnow().isoformat()
            }

            # Cache the result
            self._cache[cache_key] = result
            self._cache[f"{cache_key}_time"] = datetime.utcnow()

            logger.info(f"Fetched cuisine trends for {cuisine_type}: {result['relative_interest']}")
            return result

        except Exception as e:
            logger.error(f"PyTrends request failed for {cuisine_type}: {e}")
            return self._get_default_cuisine_trends()

    def get_local_interest(
        self,
        city: str,
        location: str = "IN",
        timeframe: str = "today 3-m"
    ) -> Dict[str, Any]:
        """
        Get restaurant interest for specific city

        Args:
            city: City name (e.g., "Gurgaon", "Mumbai", "Bangalore")
            location: Country code
            timeframe: Timeframe for trends

        Returns:
            {
                "local_interest_score": 68,  # 0-100
                "city_trend": "increasing",
                "timestamp": "2026-03-08T10:00:00Z"
            }
        """
        cache_key = f"local_interest_{city}_{location}_{timeframe}"

        # Check cache
        if self._is_cache_valid(cache_key):
            logger.info(f"Using cached local interest for {city}")
            return self._cache[cache_key]

        try:
            pytrends = self._get_pytrends()

            # City-specific restaurant keywords
            keywords = [
                f"restaurant {city}",
                f"cafe {city}",
                f"food delivery {city}"
            ]

            # Build payload
            pytrends.build_payload(
                kw_list=keywords,
                cat=0,
                timeframe=timeframe,
                geo=location,
                gprop=''
            )

            # Get interest over time
            interest_df = pytrends.interest_over_time()

            if interest_df.empty:
                logger.warning(f"No trends data for {city}")
                return self._get_default_local_interest()

            # Average across keywords
            latest_avg = interest_df[keywords].iloc[-1].mean()

            # Calculate trend
            if len(interest_df) >= 2:
                prev_avg = interest_df[keywords].iloc[-2].mean()
                change = latest_avg - prev_avg
            else:
                change = 0

            # Determine city trend
            if change > 5:
                city_trend = "increasing"
            elif change < -5:
                city_trend = "decreasing"
            else:
                city_trend = "stable"

            result = {
                "local_interest_score": int(latest_avg),
                "city_trend": city_trend,
                "change": round(change, 2),
                "timestamp": datetime.utcnow().isoformat()
            }

            # Cache the result
            self._cache[cache_key] = result
            self._cache[f"{cache_key}_time"] = datetime.utcnow()

            logger.info(f"Fetched local interest for {city}: {result['city_trend']}")
            return result

        except Exception as e:
            logger.error(f"PyTrends request failed for {city}: {e}")
            return self._get_default_local_interest()

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid"""
        time_key = f"{cache_key}_time"
        if cache_key not in self._cache or time_key not in self._cache:
            return False

        age_hours = (datetime.utcnow() - self._cache[time_key]).total_seconds() / 3600
        return age_hours < self._cache_ttl_hours

    def get_lagged_trends_for_date(
        self,
        target_date: datetime,
        lag_days: int = 1,
        location: str = "IN"
    ) -> Dict[str, Any]:
        """
        Get trends from LAG_DAYS before target date

        Critical for training: Use trends from PREVIOUS period to predict CURRENT demand.
        This avoids data leakage - we only use data available at prediction time.

        Example:
        - Target date: Oct 15, 2025
        - Lag: 1 day
        - Returns: Trends from Oct 14 (available when predicting Oct 15)

        Args:
            target_date: Date we're predicting for
            lag_days: Days to lag (1 = use yesterday's trends)
            location: Country code

        Returns:
            Trends from lagged period
        """
        # Calculate lagged date range
        # Use 7-day average ending lag_days before target
        lag_end = target_date - timedelta(days=lag_days)
        lag_start = lag_end - timedelta(days=7)

        # Format for PyTrends
        timeframe = f"{lag_start.strftime('%Y-%m-%d')} {lag_end.strftime('%Y-%m-%d')}"

        cache_key = f"lagged_trends_{target_date.date()}_{lag_days}_{location}"

        # Check cache
        if self._is_cache_valid(cache_key):
            logger.info(f"Using cached lagged trends for {target_date.date()}")
            return self._cache[cache_key]

        try:
            pytrends = self._get_pytrends()

            keywords = [
                "restaurant near me",
                "food delivery",
                "dine in restaurant",
                "cafe near me"
            ]

            pytrends.build_payload(
                kw_list=keywords,
                cat=0,
                timeframe=timeframe,
                geo=location,
                gprop=''
            )

            interest_df = pytrends.interest_over_time()

            if interest_df.empty:
                logger.warning(f"No trends data for {timeframe}")
                return self._get_default_trends()

            # Get average over the period (smoother signal)
            avg_values = interest_df[keywords].mean()

            result = {
                "restaurant_search_trend": int(avg_values["restaurant near me"]),
                "delivery_trend": int(avg_values["food delivery"]),
                "dine_in_trend": int(avg_values["dine in restaurant"]),
                "cafe_trend": int(avg_values["cafe near me"]),
                "trend_direction": "stable",  # Simplified for lagged
                "weekly_change_pct": 0.0,
                "timestamp": datetime.utcnow().isoformat(),
                "is_lagged": True,
                "lag_days": lag_days,
                "target_date": target_date.strftime("%Y-%m-%d")
            }

            # Cache
            self._cache[cache_key] = result
            self._cache[f"{cache_key}_time"] = datetime.utcnow()

            logger.info(
                f"Fetched lagged trends for {target_date.date()} "
                f"(using {lag_start.date()} to {lag_end.date()})"
            )
            return result

        except Exception as e:
            logger.error(f"PyTrends lagged request failed: {e}")
            return self._get_default_trends()

    def _get_default_trends(self) -> Dict[str, Any]:
        """Default trends when API fails"""
        return {
            "restaurant_search_trend": 50,
            "delivery_trend": 50,
            "dine_in_trend": 50,
            "cafe_trend": 50,
            "trend_direction": "stable",
            "weekly_change_pct": 0.0,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _get_default_cuisine_trends(self) -> Dict[str, Any]:
        """Default cuisine trends when API fails"""
        return {
            "cuisine_trend": 50,
            "relative_interest": "stable",
            "trend_score": 0.5,
            "change_pct": 0.0,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _get_default_local_interest(self) -> Dict[str, Any]:
        """Default local interest when API fails"""
        return {
            "local_interest_score": 50,
            "city_trend": "stable",
            "change": 0.0,
            "timestamp": datetime.utcnow().isoformat()
        }


# Singleton instance
_pytrends_service: Optional[PyTrendsService] = None


def get_pytrends_service() -> PyTrendsService:
    """Get singleton PyTrends service instance"""
    global _pytrends_service
    if _pytrends_service is None:
        _pytrends_service = PyTrendsService()
    return _pytrends_service

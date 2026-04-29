"""
Weather Service for Demand Forecasting

Provides two modes:
1. Historical weather data (for ML training)
2. Forecast weather data (for predictions)

Uses OpenWeatherMap API with aggressive caching to respect rate limits.
"""

import httpx
import logging
from datetime import datetime, timedelta
from app.utils.timezone import now_ist
from typing import Dict, List, Optional, Any
from functools import lru_cache
import json

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class WeatherService:
    """
    Weather data service using OpenWeatherMap API

    Features:
    - Historical weather (for training models)
    - 7-day forecast (for predictions)
    - Automatic caching (24-hour TTL for forecasts)
    - Rate limit protection (1000 calls/day free tier)
    """

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.OPENWEATHERMAP_API_KEY
        self.location = self.settings.RESTAURANT_LOCATION
        self._forecast_cache: Optional[Dict[str, Any]] = None
        self._forecast_cache_time: Optional[datetime] = None
        self._cache_ttl_hours = 24

    async def get_forecast_features(
        self,
        location: Optional[str] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get weather forecast for next N days with ML features

        Used for making predictions - provides FUTURE weather conditions.

        Args:
            location: Location string (e.g., "Bangalore, India")
            days: Number of days to forecast (max 5 with free tier)

        Returns:
            List of daily weather features:
            [
                {
                    "date": "2026-03-09",
                    "temp_avg": 24.5,
                    "temp_min": 20.0,
                    "temp_max": 28.0,
                    "is_rainy": True,
                    "rain_probability": 0.8,
                    "humidity": 75,
                    "wind_speed": 12.5,
                    "condition": "Rain"
                },
                ...
            ]
        """
        if not self.api_key:
            logger.warning("OpenWeatherMap API key not configured")
            return self._get_default_forecast_features(days)

        location = location or self.location

        # Check cache (24-hour TTL)
        if self._is_cache_valid():
            logger.info("Using cached weather forecast")
            return self._forecast_cache[:days]

        try:
            async with httpx.AsyncClient() as client:
                # OpenWeatherMap 5-day forecast (free tier)
                response = await client.get(
                    "https://api.openweathermap.org/data/2.5/forecast",
                    params={
                        "q": location,
                        "appid": self.api_key,
                        "units": "metric",
                        "cnt": min(days * 8, 40)  # 3-hour intervals, max 5 days
                    },
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.error(f"Weather API error: {response.status_code}")
                    return self._get_default_forecast_features(days)

                data = response.json()
                forecast_list = data.get("list", [])

                # Aggregate 3-hour intervals to daily
                daily_features = []
                for day_idx in range(0, len(forecast_list), 8):
                    day_data = forecast_list[day_idx:day_idx+8]
                    if not day_data:
                        continue

                    # Extract temperatures
                    temps = [d["main"]["temp"] for d in day_data]
                    humidities = [d["main"]["humidity"] for d in day_data]
                    wind_speeds = [d["wind"]["speed"] for d in day_data]

                    # Extract weather conditions
                    conditions = [d["weather"][0]["main"] for d in day_data]
                    rain_count = sum(1 for c in conditions if c in ["Rain", "Thunderstorm", "Drizzle"])

                    # Get rain probability (if available)
                    rain_probs = [d.get("pop", 0) for d in day_data]  # Probability of precipitation

                    daily_features.append({
                        "date": day_data[0]["dt_txt"][:10],
                        "temp_avg": round(sum(temps) / len(temps), 1),
                        "temp_min": round(min(temps), 1),
                        "temp_max": round(max(temps), 1),
                        "is_rainy": rain_count >= 3,  # If 3+ intervals have rain
                        "rain_probability": round(sum(rain_probs) / len(rain_probs), 2),
                        "humidity": round(sum(humidities) / len(humidities), 0),
                        "wind_speed": round(sum(wind_speeds) / len(wind_speeds), 1),
                        "condition": max(set(conditions), key=conditions.count)  # Most common
                    })

                # Cache the results
                self._forecast_cache = daily_features
                self._forecast_cache_time = now_ist()

                logger.info(f"Fetched weather forecast for {len(daily_features)} days")
                return daily_features[:days]

        except Exception as e:
            logger.error(f"Weather API request failed: {e}")
            return self._get_default_forecast_features(days)

    async def get_historical_features(
        self,
        location: Optional[str] = None,
        lookback_days: int = 90,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get historical weather data for ML training

        Uses Visual Crossing API (free tier: 1000 calls/day, includes historical data!)
        Fallback to stored weather history in MongoDB, then synthetic data.

        Args:
            location: Location string (e.g., "Bangalore, India")
            lookback_days: Number of days to look back (if start_date not provided)
            start_date: Specific start date for historical data
            end_date: Specific end date for historical data

        Returns:
            List of daily weather features (same format as get_forecast_features)
        """
        location = location or self.location

        # Calculate date range
        if start_date and end_date:
            pass  # Use provided dates
        elif start_date:
            end_date = now_ist()
        else:
            end_date = now_ist()
            start_date = end_date - timedelta(days=lookback_days)

        # Try Visual Crossing API first (free tier includes historical data)
        visualcrossing_key = getattr(self.settings, 'VISUALCROSSING_API_KEY', '')

        if visualcrossing_key:
            try:
                logger.info(
                    f"Fetching historical weather from Visual Crossing "
                    f"({start_date.date()} to {end_date.date()})"
                )

                historical_data = await self._fetch_visual_crossing_historical(
                    location,
                    start_date,
                    end_date,
                    visualcrossing_key
                )

                if historical_data:
                    return historical_data

            except Exception as e:
                logger.warning(f"Visual Crossing API failed: {e}")

        # Fallback: Try MongoDB weather history (if we've been storing forecasts)
        try:
            from app.core.database import get_database
            db = get_database()

            stored_weather = await db.weather_history.find({
                "date": {
                    "$gte": start_date.strftime("%Y-%m-%d"),
                    "$lte": end_date.strftime("%Y-%m-%d")
                }
            }).to_list(length=None)

            if stored_weather and len(stored_weather) >= lookback_days * 0.7:  # At least 70% coverage
                logger.info(f"Using stored weather history from MongoDB ({len(stored_weather)} days)")
                return [
                    {
                        "date": w["date"],
                        "temp_avg": w.get("temp_avg", 25.0),
                        "temp_min": w.get("temp_min", 20.0),
                        "temp_max": w.get("temp_max", 30.0),
                        "is_rainy": w.get("is_rainy", False),
                        "humidity": w.get("humidity", 50.0),
                        "wind_speed": w.get("wind_speed", 10.0)
                    }
                    for w in stored_weather
                ]

        except Exception as e:
            logger.warning(f"Failed to fetch stored weather history: {e}")

        # Last resort: Synthetic data (with warning)
        logger.warning(
            "⚠️  No real historical weather data available! Using SYNTHETIC data. "
            "This will reduce ML accuracy. Solutions: "
            "1. Add VISUALCROSSING_API_KEY to .env (free tier: 1000 calls/day) "
            "2. Run daily weather storage job to build history "
            "3. Use paid OpenWeatherMap tier ($40/month)"
        )

        # Generate synthetic historical data based on seasonal patterns
        # This is a placeholder - in production, use real historical data
        import random

        historical_features = []
        base_date = now_ist() - timedelta(days=lookback_days)

        for day_offset in range(lookback_days):
            date = base_date + timedelta(days=day_offset)

            # Simple seasonal pattern (India - hot summer, mild winter, monsoon)
            month = date.month
            if month in [6, 7, 8, 9]:  # Monsoon season
                temp_avg = random.uniform(24, 28)
                is_rainy = random.random() < 0.6  # 60% chance of rain
                humidity = random.uniform(70, 90)
            elif month in [12, 1, 2]:  # Winter
                temp_avg = random.uniform(18, 24)
                is_rainy = random.random() < 0.1  # 10% chance of rain
                humidity = random.uniform(40, 60)
            else:  # Summer
                temp_avg = random.uniform(28, 36)
                is_rainy = random.random() < 0.15  # 15% chance of rain
                humidity = random.uniform(30, 50)

            historical_features.append({
                "date": date.strftime("%Y-%m-%d"),
                "temp_avg": round(temp_avg, 1),
                "temp_min": round(temp_avg - 4, 1),
                "temp_max": round(temp_avg + 6, 1),
                "is_rainy": is_rainy,
                "rain_probability": 0.8 if is_rainy else 0.2,
                "humidity": round(humidity, 0),
                "wind_speed": round(random.uniform(5, 15), 1),
                "condition": "Rain" if is_rainy else "Clear"
            })

        return historical_features

    async def _fetch_visual_crossing_historical(
        self,
        location: str,
        start_date: datetime,
        end_date: datetime,
        api_key: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical weather from Visual Crossing API

        Visual Crossing free tier:
        - 1000 calls/day
        - Historical data included!
        - Up to 10 years of history

        Args:
            location: Location string
            start_date: Start date
            end_date: End date
            api_key: Visual Crossing API key

        Returns:
            List of daily weather features
        """
        try:
            # Format location for API (remove country, just city)
            city = location.split(",")[0].strip()

            # Format dates
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            # Visual Crossing API endpoint
            url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city}/{start_str}/{end_str}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    params={
                        "key": api_key,
                        "unitGroup": "metric",
                        "include": "days",
                        "elements": "datetime,temp,tempmin,tempmax,humidity,windspeed,precip,precipprob,conditions"
                    },
                    timeout=30.0
                )

                if response.status_code != 200:
                    logger.error(f"Visual Crossing API error: {response.status_code}")
                    return []

                data = response.json()
                days = data.get("days", [])

                historical_features = []
                for day in days:
                    # Check if it rained (precip > 0)
                    precip = day.get("precip", 0) or 0
                    is_rainy = precip > 0

                    historical_features.append({
                        "date": day["datetime"],
                        "temp_avg": round(float(day.get("temp", 25.0)), 1),
                        "temp_min": round(float(day.get("tempmin", 20.0)), 1),
                        "temp_max": round(float(day.get("tempmax", 30.0)), 1),
                        "is_rainy": is_rainy,
                        "rain_probability": round(float(day.get("precipprob", 0) or 0) / 100, 2),
                        "humidity": round(float(day.get("humidity", 50.0)), 0),
                        "wind_speed": round(float(day.get("windspeed", 10.0)), 1),
                        "condition": day.get("conditions", "Clear")
                    })

                logger.info(f"Fetched {len(historical_features)} days of historical weather from Visual Crossing")
                return historical_features

        except Exception as e:
            logger.error(f"Visual Crossing API request failed: {e}")
            return []

    def _is_cache_valid(self) -> bool:
        """Check if forecast cache is still valid"""
        if self._forecast_cache is None or self._forecast_cache_time is None:
            return False

        age_hours = (now_ist() - self._forecast_cache_time).total_seconds() / 3600
        return age_hours < self._cache_ttl_hours

    def _get_default_forecast_features(self, days: int) -> List[Dict[str, Any]]:
        """Fallback forecast when API is unavailable"""
        logger.info("Using default weather forecast (API unavailable)")

        default_features = []
        base_date = now_ist()

        for day_offset in range(days):
            date = base_date + timedelta(days=day_offset)
            default_features.append({
                "date": date.strftime("%Y-%m-%d"),
                "temp_avg": 25.0,
                "temp_min": 20.0,
                "temp_max": 30.0,
                "is_rainy": False,
                "rain_probability": 0.0,
                "humidity": 50.0,
                "wind_speed": 10.0,
                "condition": "Clear"
            })

        return default_features

    async def get_current_weather(
        self,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get current weather conditions

        Useful for real-time context in LLM reasoning.

        Args:
            location: Location string

        Returns:
            Current weather data
        """
        if not self.api_key:
            logger.warning("OpenWeatherMap API key not configured")
            return {
                "error": "Weather API not configured",
                "temperature": 25.0,
                "condition": "Unknown"
            }

        location = location or self.location

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={
                        "q": location,
                        "appid": self.api_key,
                        "units": "metric"
                    },
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.error(f"Weather API error: {response.status_code}")
                    return {"error": f"API error {response.status_code}"}

                data = response.json()

                return {
                    "temperature": data["main"]["temp"],
                    "feels_like": data["main"]["feels_like"],
                    "humidity": data["main"]["humidity"],
                    "condition": data["weather"][0]["main"],
                    "description": data["weather"][0]["description"],
                    "wind_speed": data["wind"]["speed"]
                }

        except Exception as e:
            logger.error(f"Weather API request failed: {e}")
            return {"error": str(e)}


# Singleton instance
_weather_service: Optional[WeatherService] = None


def get_weather_service() -> WeatherService:
    """Get singleton weather service instance"""
    global _weather_service
    if _weather_service is None:
        _weather_service = WeatherService()
    return _weather_service

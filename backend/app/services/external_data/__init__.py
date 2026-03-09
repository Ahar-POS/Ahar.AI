"""
External data services for demand forecasting.

This package provides services for fetching external data sources:
- Weather data (OpenWeatherMap)
- Google Trends data (PyTrends)
- News sentiment (NewsAPI)
- Local events (IPL, festivals, holidays)

All services implement caching to minimize API calls and respect rate limits.
"""

from .weather_service import WeatherService, get_weather_service
from .pytrends_service import PyTrendsService, get_pytrends_service
from .news_service import NewsService, get_news_service
from .events_service import EventsService, get_events_service

__all__ = [
    "WeatherService",
    "PyTrendsService",
    "NewsService",
    "EventsService",
    "get_weather_service",
    "get_pytrends_service",
    "get_news_service",
    "get_events_service",
]

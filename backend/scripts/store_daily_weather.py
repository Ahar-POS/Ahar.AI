"""
Daily Weather Storage Script

Run this script daily (e.g., 5:00 AM) to store weather forecasts.
Over time, these forecasts become "historical weather data" for training.

Schedule with cron:
0 5 * * * cd /path/to/backend && python scripts/store_daily_weather.py

Or use APScheduler in the orchestrator.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import get_database
from app.services.external_data import get_weather_service
from app.core.config import get_settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def store_daily_weather():
    """
    Fetch today's weather forecast and store in MongoDB

    This builds up historical weather data over time.
    """
    try:
        settings = get_settings()
        db = get_database()
        weather_service = get_weather_service()

        # Fetch 7-day forecast
        logger.info("Fetching weather forecast...")
        forecast = await weather_service.get_forecast_features(days=7)

        if not forecast:
            logger.error("Failed to fetch weather forecast")
            return False

        # Store each day in MongoDB
        stored_count = 0
        for day_weather in forecast:
            # Check if already stored
            existing = await db.weather_history.find_one({
                "date": day_weather["date"]
            })

            if existing:
                # Update existing
                await db.weather_history.update_one(
                    {"date": day_weather["date"]},
                    {
                        "$set": {
                            **day_weather,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                logger.info(f"Updated weather for {day_weather['date']}")
            else:
                # Insert new
                await db.weather_history.insert_one({
                    **day_weather,
                    "fetched_at": datetime.utcnow(),
                    "location": settings.RESTAURANT_LOCATION
                })
                stored_count += 1
                logger.info(f"Stored weather for {day_weather['date']}")

        logger.info(f"✓ Stored {stored_count} new weather records")

        # Clean up old data (keep last 180 days)
        cutoff_date = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%d")
        delete_result = await db.weather_history.delete_many({
            "date": {"$lt": cutoff_date}
        })

        if delete_result.deleted_count > 0:
            logger.info(f"Cleaned up {delete_result.deleted_count} old weather records")

        return True

    except Exception as e:
        logger.error(f"Failed to store daily weather: {e}")
        return False


async def backfill_historical_weather(days: int = 90):
    """
    Backfill historical weather data using Visual Crossing API

    This is useful for initial setup to get historical data for training.

    Args:
        days: Number of days to backfill
    """
    try:
        settings = get_settings()

        if not hasattr(settings, 'VISUALCROSSING_API_KEY') or not settings.VISUALCROSSING_API_KEY:
            logger.error(
                "Visual Crossing API key not configured. "
                "Add VISUALCROSSING_API_KEY to .env file. "
                "Get free key at: https://www.visualcrossing.com/sign-up"
            )
            return False

        db = get_database()
        weather_service = get_weather_service()

        # Fetch historical weather
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        logger.info(f"Backfilling weather data from {start_date.date()} to {end_date.date()}")

        historical_weather = await weather_service.get_historical_features(
            lookback_days=days,
            start_date=start_date,
            end_date=end_date
        )

        if not historical_weather:
            logger.error("Failed to fetch historical weather")
            return False

        # Store in MongoDB
        stored_count = 0
        for day_weather in historical_weather:
            # Check if already stored
            existing = await db.weather_history.find_one({
                "date": day_weather["date"]
            })

            if not existing:
                await db.weather_history.insert_one({
                    **day_weather,
                    "fetched_at": datetime.utcnow(),
                    "location": settings.RESTAURANT_LOCATION,
                    "is_backfilled": True
                })
                stored_count += 1

        logger.info(f"✓ Backfilled {stored_count} historical weather records")
        return True

    except Exception as e:
        logger.error(f"Failed to backfill historical weather: {e}")
        return False


if __name__ == "__main__":
    from datetime import timedelta
    import argparse

    parser = argparse.ArgumentParser(description="Store daily weather data")
    parser.add_argument(
        "--backfill",
        type=int,
        metavar="DAYS",
        help="Backfill historical weather for N days (requires Visual Crossing API key)"
    )

    args = parser.parse_args()

    if args.backfill:
        # Backfill historical data
        success = asyncio.run(backfill_historical_weather(days=args.backfill))
        sys.exit(0 if success else 1)
    else:
        # Store today's forecast
        success = asyncio.run(store_daily_weather())
        sys.exit(0 if success else 1)

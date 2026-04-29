"""IST timezone helpers — single source of truth for all date/time operations."""
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Current naive datetime in IST (stored naive for MongoDB compatibility)."""
    return datetime.now(IST).replace(tzinfo=None)

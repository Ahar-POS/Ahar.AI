"""
Events Service for Local Events

Provides data on local events that impact restaurant demand:
- IPL cricket matches (huge QSR demand spike in India)
- Indian festivals (Diwali, Holi, Eid, Christmas)
- Corporate holidays (affects lunch traffic in corporate hubs)
- Weekend patterns

No external API needed - uses hardcoded calendars for predictable events.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class EventsService:
    """
    Local events service for demand forecasting

    Events covered:
    1. IPL cricket matches (India's biggest sporting event)
    2. Major Indian festivals
    3. Corporate holidays
    4. Special occasions (Valentine's Day, New Year's Eve)

    Impact:
    - IPL final day: +20-30% demand (especially delivery)
    - Major festival (Diwali): +15-40% demand (varies by cuisine)
    - Corporate holiday: -20-30% lunch demand in corporate hubs
    """

    def __init__(self):
        self._events_cache: Dict[str, List[Dict[str, Any]]] = {}

    def get_events_for_period(
        self,
        start_date: datetime,
        end_date: datetime,
        location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all events for a specific period

        Args:
            start_date: Start date of period
            end_date: End date of period
            location: Location (for location-specific events)

        Returns:
            List of events:
            [
                {
                    "date": "2026-03-15",
                    "event_name": "Holi Festival",
                    "event_type": "festival",
                    "impact_score": 0.8,  # 0-1, higher = bigger impact
                    "impact_direction": "positive",  # positive/negative
                    "description": "Hindu festival of colors"
                },
                ...
            ]
        """
        events = []

        # Check each day in the period
        current_date = start_date
        while current_date <= end_date:
            day_events = self._get_events_for_date(current_date, location)
            events.extend(day_events)
            current_date += timedelta(days=1)

        logger.info(f"Found {len(events)} events for period {start_date} to {end_date}")
        return events

    def get_event_features_for_date(
        self,
        date: datetime,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get event features for ML models (single date)

        Args:
            date: Date to check
            location: Location (for location-specific events)

        Returns:
            {
                "is_festival": True,
                "is_ipl_match": False,
                "is_corporate_holiday": False,
                "festival_impact_score": 0.8,  # 0-1
                "total_impact_score": 0.8,  # Combined impact
                "event_names": ["Holi Festival"],
                "impact_direction": "positive"  # positive/negative
            }
        """
        events = self._get_events_for_date(date, location)

        if not events:
            return self._get_default_features()

        # Extract features
        is_festival = any(e["event_type"] == "festival" for e in events)
        is_ipl_match = any(e["event_type"] == "ipl" for e in events)
        is_corporate_holiday = any(e["event_type"] == "corporate_holiday" for e in events)

        # Calculate combined impact score
        festival_impact = max(
            [e["impact_score"] for e in events if e["event_type"] == "festival"],
            default=0.0
        )
        total_impact = sum(
            e["impact_score"] if e["impact_direction"] == "positive" else -e["impact_score"]
            for e in events
        )

        # Overall impact direction
        if total_impact > 0.1:
            impact_direction = "positive"
        elif total_impact < -0.1:
            impact_direction = "negative"
        else:
            impact_direction = "neutral"

        return {
            "is_festival": is_festival,
            "is_ipl_match": is_ipl_match,
            "is_corporate_holiday": is_corporate_holiday,
            "festival_impact_score": round(festival_impact, 2),
            "total_impact_score": round(total_impact, 2),
            "event_names": [e["event_name"] for e in events],
            "impact_direction": impact_direction
        }

    def _get_events_for_date(
        self,
        date: datetime,
        location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all events for a specific date"""
        events = []

        # Check festivals
        festival = self._check_festivals(date)
        if festival:
            events.append(festival)

        # Check IPL matches (approximate IPL season: March-May)
        ipl_event = self._check_ipl(date)
        if ipl_event:
            events.append(ipl_event)

        # Check corporate holidays
        corporate_holiday = self._check_corporate_holidays(date)
        if corporate_holiday:
            events.append(corporate_holiday)

        # Check special occasions
        special_occasion = self._check_special_occasions(date)
        if special_occasion:
            events.append(special_occasion)

        return events

    def _check_festivals(self, date: datetime) -> Optional[Dict[str, Any]]:
        """
        Check if date is a major Indian festival

        NOTE: Many Indian festivals follow lunar calendar, so dates vary yearly.
        This is a simplified hardcoded list for 2026. For production, use a
        comprehensive holiday API or lunar calendar library.
        """
        year = date.year
        month = date.month
        day = date.day

        # Major festivals (approximate dates for 2026)
        festivals = {
            # Holi (March - varies)
            (2026, 3, 14): ("Holi", 0.7, "Festival of colors, family gatherings"),

            # Eid (varies, approximate)
            (2026, 4, 4): ("Eid al-Fitr", 0.8, "End of Ramadan, family feasts"),

            # Diwali (October-November - varies)
            (2026, 11, 1): ("Diwali", 0.9, "Festival of lights, biggest festival"),

            # Christmas
            (2026, 12, 25): ("Christmas", 0.7, "Christian festival, gift giving"),

            # New Year's Eve
            (2026, 12, 31): ("New Year's Eve", 0.8, "Year-end celebrations, parties"),

            # Republic Day
            (2026, 1, 26): ("Republic Day", 0.5, "National holiday"),

            # Independence Day
            (2026, 8, 15): ("Independence Day", 0.5, "National holiday"),

            # Gandhi Jayanti
            (2026, 10, 2): ("Gandhi Jayanti", 0.4, "National holiday")
        }

        key = (year, month, day)
        if key in festivals:
            name, impact, description = festivals[key]
            return {
                "date": date.strftime("%Y-%m-%d"),
                "event_name": name,
                "event_type": "festival",
                "impact_score": impact,
                "impact_direction": "positive",
                "description": description
            }

        return None

    def _check_ipl(self, date: datetime) -> Optional[Dict[str, Any]]:
        """
        Check if date is during IPL season

        IPL (Indian Premier League) cricket is HUGE in India.
        Match days significantly increase QSR delivery orders.

        IPL season: Typically March-May (exact dates vary yearly)

        For MVP, we assume:
        - Weekend matches: Higher impact (more viewers)
        - Weekday matches: Moderate impact
        - Finals: Very high impact
        """
        year = date.year
        month = date.month

        # IPL season months (approximate)
        if month in [3, 4, 5]:
            # Check if it's a weekend (higher impact)
            is_weekend = date.weekday() >= 5  # Saturday=5, Sunday=6

            # Finals are typically in late May (approximate)
            is_finals = (month == 5 and date.day >= 20)

            if is_finals:
                impact = 0.9
                description = "IPL Finals - very high viewership"
            elif is_weekend:
                impact = 0.6
                description = "IPL Weekend Match"
            else:
                impact = 0.4
                description = "IPL Match Day"

            return {
                "date": date.strftime("%Y-%m-%d"),
                "event_name": "IPL Match",
                "event_type": "ipl",
                "impact_score": impact,
                "impact_direction": "positive",
                "description": description
            }

        return None

    def _check_corporate_holidays(self, date: datetime) -> Optional[Dict[str, Any]]:
        """
        Check if corporate offices are closed

        Important for cafes in corporate hubs (Gurgaon, Bangalore, Pune).
        Corporate holidays = -20-30% lunch demand.
        """
        # Check if it's already a weekend
        if date.weekday() >= 5:
            return None  # Weekends handled separately

        # Check if it's a national holiday (corporate offices closed)
        festival = self._check_festivals(date)
        if festival and festival["event_name"] in [
            "Republic Day", "Independence Day", "Gandhi Jayanti",
            "Diwali", "Holi", "Eid al-Fitr", "Christmas"
        ]:
            return {
                "date": date.strftime("%Y-%m-%d"),
                "event_name": f"Corporate Holiday - {festival['event_name']}",
                "event_type": "corporate_holiday",
                "impact_score": 0.3,  # -30% lunch traffic
                "impact_direction": "negative",
                "description": "Corporate offices closed, reduced lunch demand"
            }

        return None

    def _check_special_occasions(self, date: datetime) -> Optional[Dict[str, Any]]:
        """Check for special occasions (Valentine's Day, Mother's Day, etc.)"""
        year = date.year
        month = date.month
        day = date.day

        special_days = {
            (2026, 2, 14): ("Valentine's Day", 0.6, "Couples dining out"),
            (2026, 5, 10): ("Mother's Day", 0.5, "Family dining (approximate)"),
            (2026, 6, 21): ("Father's Day", 0.4, "Family dining (approximate)")
        }

        key = (year, month, day)
        if key in special_days:
            name, impact, description = special_days[key]
            return {
                "date": date.strftime("%Y-%m-%d"),
                "event_name": name,
                "event_type": "special_occasion",
                "impact_score": impact,
                "impact_direction": "positive",
                "description": description
            }

        return None

    def _get_default_features(self) -> Dict[str, Any]:
        """Default features when no events"""
        return {
            "is_festival": False,
            "is_ipl_match": False,
            "is_corporate_holiday": False,
            "festival_impact_score": 0.0,
            "total_impact_score": 0.0,
            "event_names": [],
            "impact_direction": "neutral"
        }

    def get_upcoming_events(
        self,
        days: int = 7,
        location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming events for next N days

        Useful for LLM context and dashboard displays.

        Args:
            days: Number of days to look ahead
            location: Location (for location-specific events)

        Returns:
            List of upcoming events
        """
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=days)

        return self.get_events_for_period(start_date, end_date, location)


# Singleton instance
_events_service: Optional[EventsService] = None


def get_events_service() -> EventsService:
    """Get singleton events service instance"""
    global _events_service
    if _events_service is None:
        _events_service = EventsService()
    return _events_service

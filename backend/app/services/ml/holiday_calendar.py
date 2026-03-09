"""
Indian Holiday Calendar for Restaurant Demand Forecasting

Provides major Indian holidays that significantly impact restaurant demand.
All dates are hardcoded for reliability and predictability.
"""

from datetime import datetime, date
from typing import Dict, List, Optional


class IndianHolidayCalendar:
    """
    Major Indian holidays that impact restaurant demand

    Categories:
    - National Holidays: Republic Day, Independence Day, Gandhi Jayanti
    - Religious Festivals: Diwali, Holi, Eid, Christmas, etc.
    - Regional: Specific to North India / Gurgaon area
    """

    # 2025 Holiday Calendar
    HOLIDAYS_2025 = {
        # National Holidays (restaurants often closed or very low demand)
        datetime(2025, 1, 1): {
            'name': 'New Year',
            'type': 'national',
            'impact': -0.4,  # 40% demand drop
            'description': 'Families celebrate at home'
        },
        datetime(2025, 1, 26): {
            'name': 'Republic Day',
            'type': 'national',
            'impact': -0.3,  # 30% demand drop
            'description': 'National holiday, family gatherings'
        },
        datetime(2025, 8, 15): {
            'name': 'Independence Day',
            'type': 'national',
            'impact': -0.3,
            'description': 'National holiday'
        },
        datetime(2025, 10, 2): {
            'name': 'Gandhi Jayanti',
            'type': 'national',
            'impact': -0.2,
            'description': 'Dry day, many restaurants closed'
        },

        # Major Hindu Festivals
        datetime(2025, 3, 14): {
            'name': 'Holi',
            'type': 'festival',
            'impact': -0.5,  # 50% drop - people celebrate at home
            'description': 'Festival of colors, home celebrations'
        },
        datetime(2025, 10, 20): {
            'name': 'Dussehra',
            'type': 'festival',
            'impact': -0.3,
            'description': 'Festival, family gatherings'
        },
        datetime(2025, 11, 1): {
            'name': 'Diwali',
            'type': 'festival',
            'impact': -0.6,  # 60% drop - biggest festival, everyone at home
            'description': 'Festival of lights, major home celebrations'
        },

        # Muslim Holidays (Eid dates vary, 2025 estimates)
        datetime(2025, 3, 31): {
            'name': 'Eid al-Fitr',
            'type': 'festival',
            'impact': -0.4,
            'description': 'End of Ramadan, family feasts at home'
        },
        datetime(2025, 6, 7): {
            'name': 'Eid al-Adha',
            'type': 'festival',
            'impact': -0.4,
            'description': 'Bakrid, family celebrations'
        },

        # Christmas and New Year
        datetime(2025, 12, 25): {
            'name': 'Christmas',
            'type': 'festival',
            'impact': -0.7,  # 70% drop - major holiday, most places closed
            'description': 'Christmas Day, restaurants closed or minimal operation'
        },
        datetime(2025, 12, 31): {
            'name': 'New Year Eve',
            'type': 'festival',
            'impact': +0.2,  # 20% boost - people celebrate, party orders
            'description': 'Party night, increased orders'
        },

        # Other Significant Days
        datetime(2025, 11, 5): {
            'name': 'Guru Nanak Jayanti',
            'type': 'festival',
            'impact': -0.2,
            'description': 'Sikh festival'
        },
        datetime(2025, 4, 14): {
            'name': 'Baisakhi',
            'type': 'festival',
            'impact': -0.2,
            'description': 'Harvest festival (Punjab/North India)'
        },
        datetime(2025, 8, 27): {
            'name': 'Janmashtami',
            'type': 'festival',
            'impact': -0.3,
            'description': 'Krishna birthday, fasting and celebrations'
        },
    }

    # Day before major festivals (pre-festival surge)
    PRE_FESTIVAL_SURGE = {
        datetime(2025, 10, 31): {  # Day before Diwali
            'name': 'Pre-Diwali',
            'impact': +0.3,  # 30% surge - people stock up
            'description': 'Shopping and preparation surge'
        },
        datetime(2025, 12, 24): {  # Christmas Eve
            'name': 'Christmas Eve',
            'impact': +0.1,  # 10% surge - some celebration orders
            'description': 'Pre-Christmas preparations'
        },
        datetime(2025, 3, 13): {  # Day before Holi
            'name': 'Pre-Holi',
            'impact': +0.2,
            'description': 'Holi preparation shopping'
        },
    }

    @classmethod
    def get_holiday(cls, date_obj: datetime) -> Optional[Dict]:
        """
        Get holiday information for a specific date

        Args:
            date_obj: Date to check

        Returns:
            Holiday info dict or None
        """
        # Check main holidays
        if date_obj in cls.HOLIDAYS_2025:
            return cls.HOLIDAYS_2025[date_obj]

        # Check pre-festival days
        if date_obj in cls.PRE_FESTIVAL_SURGE:
            return cls.PRE_FESTIVAL_SURGE[date_obj]

        return None

    @classmethod
    def is_holiday(cls, date_obj: datetime) -> bool:
        """Check if date is a holiday"""
        return date_obj in cls.HOLIDAYS_2025

    @classmethod
    def is_major_festival(cls, date_obj: datetime) -> bool:
        """Check if date is a major festival (Diwali, Holi, Christmas, Eid)"""
        holiday = cls.get_holiday(date_obj)
        if holiday:
            return holiday['name'] in ['Diwali', 'Holi', 'Christmas', 'Eid al-Fitr', 'Eid al-Adha']
        return False

    @classmethod
    def get_impact_score(cls, date_obj: datetime) -> float:
        """
        Get demand impact for a date

        Returns:
            Float between -1.0 (complete closure) and +1.0 (double demand)
            0.0 = normal day
            -0.5 = 50% demand drop
            +0.3 = 30% demand increase
        """
        holiday = cls.get_holiday(date_obj)
        if holiday:
            return holiday['impact']
        return 0.0

    @classmethod
    def add_holiday_features(cls, df) -> 'pd.DataFrame':
        """
        Add holiday features to dataframe

        Args:
            df: DataFrame with 'ds' column (date)

        Returns:
            DataFrame with holiday features added
        """
        import pandas as pd

        df = df.copy()

        # Initialize features
        df['is_holiday'] = 0
        df['is_major_festival'] = 0
        df['holiday_impact_score'] = 0.0
        df['is_pre_festival'] = 0
        df['holiday_name'] = ''

        # Apply holiday information
        for idx, row in df.iterrows():
            date_val = row['ds']

            # Main holiday
            holiday = cls.get_holiday(date_val)
            if holiday:
                df.at[idx, 'is_holiday'] = 1
                df.at[idx, 'holiday_impact_score'] = holiday['impact']
                df.at[idx, 'holiday_name'] = holiday['name']

                # Major festival flag
                if holiday['name'] in ['Diwali', 'Holi', 'Christmas', 'Eid al-Fitr', 'Eid al-Adha']:
                    df.at[idx, 'is_major_festival'] = 1

                # Pre-festival flag
                if date_val in cls.PRE_FESTIVAL_SURGE:
                    df.at[idx, 'is_pre_festival'] = 1

        return df

    @classmethod
    def get_all_holidays(cls, year: int = 2025) -> List[Dict]:
        """Get list of all holidays for a year"""
        if year == 2025:
            return [
                {'date': k, **v}
                for k, v in sorted(cls.HOLIDAYS_2025.items())
            ]
        return []


def get_holiday_calendar() -> IndianHolidayCalendar:
    """Get holiday calendar instance"""
    return IndianHolidayCalendar()


# Quick test
if __name__ == "__main__":
    calendar = IndianHolidayCalendar()

    # Test dates
    test_dates = [
        datetime(2025, 12, 25),  # Christmas
        datetime(2025, 11, 1),   # Diwali
        datetime(2025, 3, 14),   # Holi
        datetime(2025, 10, 15),  # Normal day
    ]

    print("Holiday Calendar Test:")
    print("=" * 60)
    for date_val in test_dates:
        holiday = calendar.get_holiday(date_val)
        if holiday:
            print(f"{date_val.strftime('%Y-%m-%d')}: {holiday['name']} (impact: {holiday['impact']:+.1%})")
        else:
            print(f"{date_val.strftime('%Y-%m-%d')}: Normal day")

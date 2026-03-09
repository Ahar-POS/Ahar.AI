"""
Outlier Detector for Time Series Data

Detects and handles outliers in historical order data using IQR (Interquartile Range) method.

Outliers are typically:
- Special events (IPL finals, festivals not in training data)
- Data errors (duplicate orders, wrong quantities)
- One-off promotions
- System issues (POS downtime)

Strategy:
- Flag outliers (don't remove - might be legitimate)
- Option to remove for training (improves model stability)
- Option to create separate "special event" model
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class OutlierDetector:
    """
    IQR-based outlier detection for time series demand data

    Uses Interquartile Range (IQR) method:
    - Q1 (25th percentile), Q3 (75th percentile)
    - IQR = Q3 - Q1
    - Outliers: values < Q1 - 1.5*IQR OR values > Q3 + 1.5*IQR

    Configurable multiplier (default 1.5):
    - Lower multiplier (1.0) = more aggressive outlier detection
    - Higher multiplier (2.0) = more conservative
    """

    def __init__(self, iqr_multiplier: float = 1.5):
        """
        Initialize outlier detector

        Args:
            iqr_multiplier: IQR multiplier for outlier threshold (default 1.5)
        """
        self.iqr_multiplier = iqr_multiplier

    def detect_outliers(
        self,
        data: pd.DataFrame,
        value_column: str = "y",
        date_column: str = "ds"
    ) -> pd.DataFrame:
        """
        Detect outliers in time series data

        Args:
            data: DataFrame with time series data
            value_column: Column name for values (default "y" for Prophet format)
            date_column: Column name for dates (default "ds" for Prophet format)

        Returns:
            DataFrame with additional columns:
            - is_outlier: boolean flag
            - outlier_score: how many IQRs away from median (0 = not outlier)
            - outlier_type: "high" or "low" (if outlier)
        """
        if data.empty or len(data) < 4:
            logger.warning("Insufficient data for outlier detection (need >= 4 points)")
            data["is_outlier"] = False
            data["outlier_score"] = 0.0
            data["outlier_type"] = None
            return data

        # Make a copy to avoid modifying original
        result = data.copy()

        # Calculate IQR
        Q1 = result[value_column].quantile(0.25)
        Q3 = result[value_column].quantile(0.75)
        IQR = Q3 - Q1

        # Calculate outlier thresholds
        lower_threshold = Q1 - self.iqr_multiplier * IQR
        upper_threshold = Q3 + self.iqr_multiplier * IQR

        # Detect outliers
        result["is_outlier"] = (
            (result[value_column] < lower_threshold) |
            (result[value_column] > upper_threshold)
        )

        # Calculate outlier score (how many IQRs away from median)
        median = result[value_column].median()
        if IQR > 0:
            result["outlier_score"] = np.abs(result[value_column] - median) / IQR
        else:
            result["outlier_score"] = 0.0

        # Determine outlier type
        result["outlier_type"] = None
        result.loc[result[value_column] > upper_threshold, "outlier_type"] = "high"
        result.loc[result[value_column] < lower_threshold, "outlier_type"] = "low"

        outlier_count = result["is_outlier"].sum()
        outlier_pct = (outlier_count / len(result)) * 100

        logger.info(
            f"Detected {outlier_count} outliers ({outlier_pct:.1f}%) "
            f"using IQR multiplier {self.iqr_multiplier}"
        )

        return result

    def remove_outliers(
        self,
        data: pd.DataFrame,
        value_column: str = "y"
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Remove outliers from data

        Args:
            data: DataFrame with time series data
            value_column: Column name for values

        Returns:
            (clean_data, outliers) - two DataFrames
        """
        # First detect outliers
        data_with_flags = self.detect_outliers(data, value_column)

        # Split into clean and outlier data
        clean_data = data_with_flags[~data_with_flags["is_outlier"]].copy()
        outliers = data_with_flags[data_with_flags["is_outlier"]].copy()

        logger.info(
            f"Removed {len(outliers)} outliers, kept {len(clean_data)} clean samples"
        )

        return clean_data, outliers

    def get_outlier_summary(
        self,
        data: pd.DataFrame,
        value_column: str = "y",
        date_column: str = "ds"
    ) -> Dict[str, Any]:
        """
        Get summary statistics about outliers

        Args:
            data: DataFrame with time series data
            value_column: Column name for values
            date_column: Column name for dates

        Returns:
            Summary dictionary with outlier statistics
        """
        data_with_flags = self.detect_outliers(data, value_column, date_column)

        outliers = data_with_flags[data_with_flags["is_outlier"]]

        if outliers.empty:
            return {
                "outlier_count": 0,
                "outlier_percentage": 0.0,
                "high_outliers": 0,
                "low_outliers": 0,
                "outlier_dates": [],
                "outlier_values": []
            }

        high_outliers = outliers[outliers["outlier_type"] == "high"]
        low_outliers = outliers[outliers["outlier_type"] == "low"]

        return {
            "outlier_count": len(outliers),
            "outlier_percentage": round((len(outliers) / len(data)) * 100, 2),
            "high_outliers": len(high_outliers),
            "low_outliers": len(low_outliers),
            "outlier_dates": outliers[date_column].tolist(),
            "outlier_values": outliers[value_column].tolist(),
            "max_outlier_score": float(outliers["outlier_score"].max()),
            "mean_outlier_score": float(outliers["outlier_score"].mean())
        }

    def flag_outliers_with_context(
        self,
        data: pd.DataFrame,
        value_column: str = "y",
        date_column: str = "ds",
        event_dates: Optional[List[datetime]] = None
    ) -> pd.DataFrame:
        """
        Flag outliers and check if they coincide with known events

        This helps distinguish:
        - Legitimate outliers (IPL final, festival) → Keep for "special event" model
        - Data errors (duplicate orders, wrong quantities) → Remove from training

        Args:
            data: DataFrame with time series data
            value_column: Column name for values
            date_column: Column name for dates
            event_dates: List of known event dates

        Returns:
            DataFrame with additional column:
            - is_event_outlier: True if outlier coincides with known event
        """
        data_with_flags = self.detect_outliers(data, value_column, date_column)

        if event_dates is None:
            data_with_flags["is_event_outlier"] = False
            return data_with_flags

        # Convert event dates to date strings for comparison
        event_date_strings = set(
            d.strftime("%Y-%m-%d") if isinstance(d, datetime) else str(d)
            for d in event_dates
        )

        # Check if outlier dates match event dates
        def is_event_outlier(row):
            if not row["is_outlier"]:
                return False

            # Convert date to string for comparison
            date_str = (
                row[date_column].strftime("%Y-%m-%d")
                if isinstance(row[date_column], datetime)
                else str(row[date_column])
            )

            return date_str in event_date_strings

        data_with_flags["is_event_outlier"] = data_with_flags.apply(
            is_event_outlier, axis=1
        )

        event_outliers = data_with_flags[data_with_flags["is_event_outlier"]].shape[0]
        logger.info(
            f"Found {event_outliers} outliers that coincide with known events "
            f"(legitimate demand spikes)"
        )

        return data_with_flags


# Singleton instance
_outlier_detector: Optional[OutlierDetector] = None


def get_outlier_detector(iqr_multiplier: float = 1.5) -> OutlierDetector:
    """
    Get outlier detector instance

    Args:
        iqr_multiplier: IQR multiplier for outlier threshold

    Returns:
        OutlierDetector instance
    """
    global _outlier_detector
    if _outlier_detector is None or _outlier_detector.iqr_multiplier != iqr_multiplier:
        _outlier_detector = OutlierDetector(iqr_multiplier)
    return _outlier_detector

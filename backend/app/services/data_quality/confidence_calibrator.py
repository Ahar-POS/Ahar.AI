"""
Confidence Calibrator for Forecast Predictions

Calibrates prediction intervals using historical forecast errors.

Problem: Prophet/XGBoost confidence intervals measure uncertainty,
         but don't reflect actual accuracy.

Solution: Backtest predictions, learn true error distribution,
          calibrate confidence scores to reflect real accuracy.

Example:
- Prophet says 80% confidence interval: [90, 110]
- Actual historical accuracy at "80% confidence": 65% (under-confident!)
- Calibrator adjusts: "Real confidence for this interval width: 65%"
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ConfidenceCalibrator:
    """
    Calibrates prediction confidence scores using historical errors

    Process:
    1. During backtesting: Record (predicted, actual, confidence_interval_width)
    2. Build calibration curve: interval_width → actual coverage
    3. During prediction: Use calibration curve to adjust confidence

    Benefits:
    - More accurate risk assessment
    - Better safety stock decisions
    - Trust calibration for users
    """

    def __init__(self):
        self.calibration_data: List[Dict[str, float]] = []
        self.is_calibrated = False

    def add_forecast_result(
        self,
        predicted: float,
        actual: float,
        lower_bound: float,
        upper_bound: float,
        model_name: Optional[str] = None
    ) -> None:
        """
        Add a forecast result for calibration

        Call this during backtesting for each prediction.

        Args:
            predicted: Predicted value
            actual: Actual observed value
            lower_bound: Lower confidence bound
            upper_bound: Upper confidence bound
            model_name: Model that made prediction (for per-model calibration)
        """
        # Calculate metrics
        interval_width = upper_bound - lower_bound
        interval_width_pct = (interval_width / predicted) * 100 if predicted > 0 else 0

        error = abs(predicted - actual)
        error_pct = (error / actual) * 100 if actual > 0 else 0

        # Check if actual fell within interval
        is_covered = lower_bound <= actual <= upper_bound

        self.calibration_data.append({
            "predicted": predicted,
            "actual": actual,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "interval_width": interval_width,
            "interval_width_pct": interval_width_pct,
            "error": error,
            "error_pct": error_pct,
            "is_covered": is_covered,
            "model_name": model_name or "unknown"
        })

    def build_calibration_curve(self) -> Dict[str, Any]:
        """
        Build calibration curve from collected forecast results

        Returns:
            Calibration statistics and curve
        """
        if not self.calibration_data:
            logger.warning("No calibration data available")
            return self._get_default_calibration()

        df = pd.DataFrame(self.calibration_data)

        # Group by interval width percentiles
        # Bin predictions into interval width buckets
        df["width_bucket"] = pd.qcut(
            df["interval_width_pct"],
            q=5,  # 5 bins: 0-20%, 20-40%, 40-60%, 60-80%, 80-100%
            labels=["very_narrow", "narrow", "medium", "wide", "very_wide"],
            duplicates='drop'
        )

        # Calculate actual coverage for each bucket
        calibration_curve = {}
        for bucket in df["width_bucket"].unique():
            bucket_data = df[df["width_bucket"] == bucket]

            actual_coverage = bucket_data["is_covered"].mean() * 100
            avg_error_pct = bucket_data["error_pct"].mean()
            avg_width_pct = bucket_data["interval_width_pct"].mean()

            calibration_curve[str(bucket)] = {
                "actual_coverage_pct": round(actual_coverage, 1),
                "avg_error_pct": round(avg_error_pct, 1),
                "avg_width_pct": round(avg_width_pct, 1),
                "sample_count": len(bucket_data)
            }

        # Overall statistics
        overall_coverage = df["is_covered"].mean() * 100
        overall_error = df["error_pct"].mean()

        self.is_calibrated = True

        logger.info(
            f"Built calibration curve from {len(df)} forecasts. "
            f"Overall coverage: {overall_coverage:.1f}%"
        )

        return {
            "is_calibrated": True,
            "sample_count": len(df),
            "overall_coverage_pct": round(overall_coverage, 1),
            "overall_error_pct": round(overall_error, 1),
            "calibration_curve": calibration_curve
        }

    def calibrate_confidence(
        self,
        predicted: float,
        lower_bound: float,
        upper_bound: float
    ) -> Dict[str, Any]:
        """
        Calibrate confidence score for a new prediction

        Args:
            predicted: Predicted value
            lower_bound: Lower confidence bound
            upper_bound: Upper confidence bound

        Returns:
            {
                "original_confidence": 0.80,  # Model's claimed confidence
                "calibrated_confidence": 0.65,  # Actual expected confidence
                "confidence_level": "medium",  # high/medium/low
                "interval_width_pct": 22.5
            }
        """
        if not self.is_calibrated:
            logger.warning("Calibrator not trained, using default confidence")
            return self._get_default_confidence_score(predicted, lower_bound, upper_bound)

        # Calculate interval width
        interval_width = upper_bound - lower_bound
        interval_width_pct = (interval_width / predicted) * 100 if predicted > 0 else 0

        # Determine bucket
        if interval_width_pct < 15:
            bucket = "very_narrow"
        elif interval_width_pct < 25:
            bucket = "narrow"
        elif interval_width_pct < 40:
            bucket = "medium"
        elif interval_width_pct < 60:
            bucket = "wide"
        else:
            bucket = "very_wide"

        # Get calibration data for this bucket
        calibration_stats = self.build_calibration_curve()
        curve = calibration_stats.get("calibration_curve", {})

        if bucket in curve:
            calibrated_coverage = curve[bucket]["actual_coverage_pct"] / 100
        else:
            # Fallback to overall coverage
            calibrated_coverage = calibration_stats["overall_coverage_pct"] / 100

        # Determine confidence level
        if calibrated_coverage >= 0.75:
            confidence_level = "high"
        elif calibrated_coverage >= 0.55:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        # Original confidence (assume model claims 80% for typical intervals)
        original_confidence = 0.80

        return {
            "original_confidence": original_confidence,
            "calibrated_confidence": round(calibrated_coverage, 2),
            "confidence_level": confidence_level,
            "interval_width_pct": round(interval_width_pct, 1),
            "bucket": bucket
        }

    def get_confidence_level(
        self,
        predicted: float,
        lower_bound: float,
        upper_bound: float
    ) -> str:
        """
        Get simple confidence level: high/medium/low

        Args:
            predicted: Predicted value
            lower_bound: Lower confidence bound
            upper_bound: Upper confidence bound

        Returns:
            "high" / "medium" / "low"
        """
        confidence_data = self.calibrate_confidence(predicted, lower_bound, upper_bound)
        return confidence_data["confidence_level"]

    def get_calibration_report(self) -> Dict[str, Any]:
        """
        Get detailed calibration report

        Returns:
            Comprehensive calibration statistics
        """
        if not self.calibration_data:
            return {
                "status": "not_calibrated",
                "message": "No calibration data available"
            }

        df = pd.DataFrame(self.calibration_data)

        return {
            "status": "calibrated",
            "total_forecasts": len(df),
            "overall_coverage_pct": round(df["is_covered"].mean() * 100, 1),
            "mean_error_pct": round(df["error_pct"].mean(), 1),
            "median_error_pct": round(df["error_pct"].median(), 1),
            "calibration_curve": self.build_calibration_curve()
        }

    def _get_default_calibration(self) -> Dict[str, Any]:
        """Default calibration when no data available"""
        return {
            "is_calibrated": False,
            "sample_count": 0,
            "overall_coverage_pct": 70.0,  # Assume 70% as default
            "overall_error_pct": 20.0,
            "calibration_curve": {}
        }

    def _get_default_confidence_score(
        self,
        predicted: float,
        lower_bound: float,
        upper_bound: float
    ) -> Dict[str, Any]:
        """Default confidence when not calibrated"""
        interval_width = upper_bound - lower_bound
        interval_width_pct = (interval_width / predicted) * 100 if predicted > 0 else 0

        # Simple heuristic: narrower intervals = higher confidence
        if interval_width_pct < 20:
            confidence_level = "high"
            calibrated_confidence = 0.75
        elif interval_width_pct < 40:
            confidence_level = "medium"
            calibrated_confidence = 0.60
        else:
            confidence_level = "low"
            calibrated_confidence = 0.45

        return {
            "original_confidence": 0.80,
            "calibrated_confidence": calibrated_confidence,
            "confidence_level": confidence_level,
            "interval_width_pct": round(interval_width_pct, 1),
            "bucket": "unknown"
        }

    def reset(self) -> None:
        """Reset calibration data"""
        self.calibration_data = []
        self.is_calibrated = False
        logger.info("Confidence calibrator reset")


# Singleton instance
_confidence_calibrator: Optional[ConfidenceCalibrator] = None


def get_confidence_calibrator() -> ConfidenceCalibrator:
    """Get singleton confidence calibrator instance"""
    global _confidence_calibrator
    if _confidence_calibrator is None:
        _confidence_calibrator = ConfidenceCalibrator()
    return _confidence_calibrator

"""
Data Quality Services for ML Demand Forecasting

This package provides data quality and preparation services:
- Outlier detection (IQR method)
- Confidence calibration (prediction intervals)
- Data tier classification (categorize cafe by data availability)

These services improve ML accuracy by cleaning training data and setting
appropriate expectations for predictions.
"""

from .outlier_detector import OutlierDetector, get_outlier_detector
from .confidence_calibrator import ConfidenceCalibrator, get_confidence_calibrator
from .data_tier_classifier import DataTierClassifier, get_data_tier_classifier

__all__ = [
    "OutlierDetector",
    "get_outlier_detector",
    "ConfidenceCalibrator",
    "get_confidence_calibrator",
    "DataTierClassifier",
    "get_data_tier_classifier",
]

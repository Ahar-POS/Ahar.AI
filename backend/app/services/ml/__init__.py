"""
ML Services for Demand Forecasting

This package provides the machine learning infrastructure for demand forecasting:
- Base forecaster interface
- Model registry (storage and versioning)
- Individual forecasters (Prophet, SARIMA, XGBoost)
- Ensemble predictor (combines multiple models)
- Tier-based forecaster (adapts to data availability)
- Time series utilities (stationarity testing, differencing)
- Training pipeline and hyperparameter tuning
"""

from .base_forecaster import BaseForecaster
from .model_registry import ModelRegistry, get_model_registry
from .time_series_utils import TimeSeriesUtils, get_time_series_utils
from .ensemble_predictor import EnsemblePredictor
from .tier_based_forecaster import TierBasedForecaster
from .training_pipeline import TrainingPipeline
from .hyperparameter_tuner import HyperparameterTuner

__all__ = [
    "BaseForecaster",
    "ModelRegistry",
    "get_model_registry",
    "TimeSeriesUtils",
    "get_time_series_utils",
    "EnsemblePredictor",
    "TierBasedForecaster",
    "TrainingPipeline",
    "HyperparameterTuner",
]

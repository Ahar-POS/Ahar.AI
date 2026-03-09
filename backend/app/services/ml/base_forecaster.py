"""
Base Forecaster Interface

Abstract base class for all forecasting models (Prophet, SARIMA, XGBoost).
Ensures consistent API across different model types for easy ensemble integration.
"""

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseForecaster(ABC):
    """
    Abstract base class for all forecasting models

    All forecasters must implement:
    - fit(): Train the model on historical data
    - predict(): Make predictions for future periods
    - get_feature_importance(): Return feature importance (if applicable)
    - serialize(): Save model to disk
    - deserialize(): Load model from disk

    Standard interface enables ensemble methods to combine different model types.
    """

    def __init__(self, model_name: str):
        """
        Initialize forecaster

        Args:
            model_name: Name of the model (e.g., "prophet", "sarima", "xgboost")
        """
        self.model_name = model_name
        self.model = None
        self.is_fitted = False
        self.training_metadata: Dict[str, Any] = {}

    @abstractmethod
    def fit(
        self,
        train_data: pd.DataFrame,
        target_column: str = "y",
        date_column: str = "ds",
        exogenous_features: Optional[List[str]] = None,
        hyperparameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Train the model on historical data

        Args:
            train_data: Training data with date and target columns
            target_column: Name of target variable column (default "y" for Prophet)
            date_column: Name of date column (default "ds" for Prophet)
            exogenous_features: List of external feature columns (weather, events, etc.)
            hyperparameters: Model-specific hyperparameters

        Returns:
            Training metrics (MAE, RMSE, etc.)
        """
        pass

    @abstractmethod
    def predict(
        self,
        horizon: int,
        exogenous_future: Optional[pd.DataFrame] = None,
        return_confidence: bool = True
    ) -> pd.DataFrame:
        """
        Make predictions for future periods

        Args:
            horizon: Number of periods to forecast
            exogenous_future: Future values of external features (if model uses them)
            return_confidence: Whether to return confidence intervals

        Returns:
            DataFrame with columns:
            - ds: date
            - yhat: predicted value
            - yhat_lower: lower confidence bound (if return_confidence=True)
            - yhat_upper: upper confidence bound (if return_confidence=True)
        """
        pass

    @abstractmethod
    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """
        Get feature importance (if applicable)

        Returns:
            Dictionary mapping feature names to importance scores
            Returns None if model doesn't support feature importance
        """
        pass

    @abstractmethod
    def serialize(self, filepath: str) -> bool:
        """
        Save model to disk

        Args:
            filepath: Path to save model

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def deserialize(self, filepath: str) -> bool:
        """
        Load model from disk

        Args:
            filepath: Path to load model from

        Returns:
            True if successful, False otherwise
        """
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get model metadata

        Returns:
            Dictionary with model information
        """
        return {
            "model_name": self.model_name,
            "is_fitted": self.is_fitted,
            "training_metadata": self.training_metadata
        }

    def validate_data(
        self,
        data: pd.DataFrame,
        target_column: str = "y",
        date_column: str = "ds"
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate input data

        Args:
            data: Input DataFrame
            target_column: Target variable column name
            date_column: Date column name

        Returns:
            (is_valid, error_message)
        """
        if data.empty:
            return False, "Data is empty"

        if date_column not in data.columns:
            return False, f"Date column '{date_column}' not found"

        if target_column not in data.columns:
            return False, f"Target column '{target_column}' not found"

        # Check for missing values in target
        if data[target_column].isnull().any():
            missing_count = data[target_column].isnull().sum()
            return False, f"Target column has {missing_count} missing values"

        # Check for sufficient data points
        if len(data) < 14:
            return False, f"Insufficient data: {len(data)} points (need >= 14)"

        return True, None

    def calculate_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, float]:
        """
        Calculate forecast accuracy metrics

        Args:
            y_true: Actual values
            y_pred: Predicted values

        Returns:
            Dictionary with MAE, RMSE, MAPE, R²
        """
        # Remove any NaN values
        mask = ~(np.isnan(y_true) | np.isnan(y_pred))
        y_true = y_true[mask]
        y_pred = y_pred[mask]

        if len(y_true) == 0:
            return {
                "mae": float('inf'),
                "rmse": float('inf'),
                "mape": float('inf'),
                "r2": 0.0
            }

        # Mean Absolute Error
        mae = np.mean(np.abs(y_true - y_pred))

        # Root Mean Squared Error
        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))

        # Mean Absolute Percentage Error
        # Avoid division by zero
        mape_values = np.abs((y_true - y_pred) / np.maximum(y_true, 1e-10)) * 100
        mape = np.mean(mape_values)

        # R² Score
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return {
            "mae": round(float(mae), 2),
            "rmse": round(float(rmse), 2),
            "mape": round(float(mape), 2),
            "r2": round(float(r2), 4)
        }

    def __str__(self) -> str:
        return f"{self.model_name.upper()}Forecaster(fitted={self.is_fitted})"

    def __repr__(self) -> str:
        return self.__str__()

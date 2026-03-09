"""
Prophet Forecaster

Implements BaseForecaster using Facebook Prophet with exogenous regressors.

Best for:
- Weekly/monthly seasonality
- Holiday effects
- External regressors (weather, events)
- Interpretable forecasts

Tier compatibility:
- Tier 2 (14-30 days): Lightweight Prophet (weekly seasonality only)
- Tier 3+ (30+ days): Full Prophet with all features
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Any

from app.services.ml.base_forecaster import BaseForecaster
from app.services.ml.prophet_enhanced import ProphetEnhanced

logger = logging.getLogger(__name__)


class ProphetForecaster(BaseForecaster):
    """
    Prophet-based forecaster with external regressors

    Features:
    - Automatic trend detection
    - Multiple seasonality patterns (weekly, yearly)
    - Holiday effects (Indian holidays)
    - External regressors (weather, PyTrends, events)
    - Confidence intervals
    """

    def __init__(
        self,
        data_tier: str = "tier_4",
        **prophet_params
    ):
        """
        Initialize Prophet forecaster

        Args:
            data_tier: Data availability tier (tier_1 to tier_5)
            **prophet_params: Prophet hyperparameters
        """
        super().__init__(model_name="prophet")
        self.data_tier = data_tier
        self.prophet_params = prophet_params
        self.prophet_model: Optional[ProphetEnhanced] = None

    def fit(
        self,
        train_data: pd.DataFrame,
        target_column: str = "y",
        date_column: str = "ds",
        exogenous_features: Optional[List[str]] = None,
        hyperparameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Train Prophet model

        Args:
            train_data: Training data
            target_column: Target variable column name
            date_column: Date column name
            exogenous_features: External features (weather, events, trends)
            hyperparameters: Prophet hyperparameters

        Returns:
            Training metrics
        """
        # Validate data
        is_valid, error_msg = self.validate_data(train_data, target_column, date_column)
        if not is_valid:
            raise ValueError(f"Invalid training data: {error_msg}")

        # Prepare hyperparameters based on data tier
        params = self._get_tier_specific_params()
        if hyperparameters:
            params.update(hyperparameters)

        # Initialize Prophet
        self.prophet_model = ProphetEnhanced(**params)

        # Add India holidays
        self.prophet_model.add_country_holidays("IN")

        # Prepare data for Prophet
        prophet_data = train_data[[date_column, target_column]].copy()
        prophet_data.columns = ["ds", "y"]

        # Add exogenous features
        if exogenous_features:
            for feature in exogenous_features:
                if feature in train_data.columns:
                    prophet_data[feature] = train_data[feature].values

        # Fit model
        fit_stats = self.prophet_model.fit(prophet_data, regressors=exogenous_features)

        # Calculate training metrics (in-sample)
        train_predictions = self.prophet_model.model.predict(prophet_data)
        y_true = prophet_data["y"].values
        y_pred = train_predictions["yhat"].values

        metrics = self.calculate_metrics(y_true, y_pred)

        # Store metadata
        self.training_metadata = {
            "data_points": len(train_data),
            "features_used": exogenous_features or [],
            "data_tier": self.data_tier,
            "hyperparameters": params,
            "metrics": metrics
        }

        self.is_fitted = True

        logger.info(
            f"Prophet trained on {len(train_data)} points, "
            f"MAPE: {metrics['mape']:.2f}%"
        )

        return metrics

    def predict(
        self,
        horizon: int,
        exogenous_future: Optional[pd.DataFrame] = None,
        return_confidence: bool = True
    ) -> pd.DataFrame:
        """
        Make predictions

        Args:
            horizon: Number of days to forecast
            exogenous_future: Future values of external features
            return_confidence: Whether to return confidence intervals

        Returns:
            DataFrame with predictions
        """
        if not self.is_fitted or self.prophet_model is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Make predictions
        forecast = self.prophet_model.predict(
            periods=horizon,
            freq="D",
            future_regressors=exogenous_future
        )

        if not return_confidence:
            forecast = forecast[["ds", "yhat"]]

        return forecast

    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """
        Get regressor contributions

        Returns:
            Dictionary mapping feature names to contributions
        """
        if not self.is_fitted or self.prophet_model is None:
            return None

        return self.prophet_model.get_regressor_contributions()

    def serialize(self, filepath: str) -> bool:
        """
        Save model to disk

        Args:
            filepath: Path to save model (JSON format)

        Returns:
            True if successful
        """
        if not self.is_fitted or self.prophet_model is None:
            logger.error("Cannot serialize unfitted model")
            return False

        return self.prophet_model.serialize(filepath)

    def deserialize(self, filepath: str) -> bool:
        """
        Load model from disk

        Args:
            filepath: Path to load model from

        Returns:
            True if successful
        """
        self.prophet_model = ProphetEnhanced()
        success = self.prophet_model.deserialize(filepath)

        if success:
            self.is_fitted = True

        return success

    def _get_tier_specific_params(self) -> Dict[str, Any]:
        """
        Get Prophet hyperparameters optimized for data tier

        Returns:
            Prophet parameters
        """
        if self.data_tier == "tier_1":
            # <14 days: Not recommended (use category baseline instead)
            return {
                "changepoint_prior_scale": 0.01,  # Very conservative
                "seasonality_prior_scale": 5.0,
                "weekly_seasonality": False,
                "yearly_seasonality": False,
                "daily_seasonality": False
            }

        elif self.data_tier == "tier_2":
            # 14-30 days: Lightweight Prophet
            return {
                "changepoint_prior_scale": 0.03,  # Conservative
                "seasonality_prior_scale": 8.0,
                "weekly_seasonality": True,  # Weekly patterns only
                "yearly_seasonality": False,
                "daily_seasonality": False
            }

        elif self.data_tier == "tier_3":
            # 30-60 days: Moderate Prophet
            return {
                "changepoint_prior_scale": 0.05,  # Balanced
                "seasonality_prior_scale": 10.0,
                "weekly_seasonality": True,
                "yearly_seasonality": False,  # Not enough data
                "daily_seasonality": False
            }

        else:  # tier_4, tier_5 (60+ days)
            # Full Prophet
            return {
                "changepoint_prior_scale": 0.05,
                "seasonality_prior_scale": 10.0,
                "weekly_seasonality": True,
                "yearly_seasonality": False,  # Need 2+ years for this
                "daily_seasonality": False
            }

    def get_prediction_components(
        self,
        horizon: int,
        exogenous_future: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Get prediction breakdown (trend + seasonality + regressors)

        Useful for understanding what drives predictions.

        Args:
            horizon: Number of days to forecast
            exogenous_future: Future external features

        Returns:
            DataFrame with component breakdown
        """
        if not self.is_fitted or self.prophet_model is None:
            raise ValueError("Model not fitted")

        return self.prophet_model.predict_with_components(
            periods=horizon,
            freq="D",
            future_regressors=exogenous_future
        )

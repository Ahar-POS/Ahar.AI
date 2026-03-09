"""
SARIMA Forecaster

Implements BaseForecaster using SARIMA (Seasonal ARIMA).

Best for:
- Stationary time series
- Strong periodic patterns
- When trends are linear
- Stable items with predictable demand

Requirements:
- Minimum 60 days of data (for stationarity testing)
- Stationary or nearly stationary data
- Clear seasonal patterns

Tier compatibility:
- Tier 4+ (60+ days): Full SARIMA
- Tier 3 and below: Skip SARIMA (use Prophet/XGBoost instead)
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Any
import joblib

from statsmodels.tsa.statespace.sarimax import SARIMAX
from itertools import product
import warnings
warnings.filterwarnings('ignore')

from app.services.ml.base_forecaster import BaseForecaster
from app.services.ml.time_series_utils import TimeSeriesUtils

logger = logging.getLogger(__name__)


class SARIMAForecaster(BaseForecaster):
    """
    SARIMA-based forecaster

    Features:
    - Automatic stationarity testing
    - Auto-ARIMA for parameter selection
    - Seasonal patterns
    - Pure time-series (no external features)

    Note: SARIMA does NOT use external features (weather, events).
          It relies purely on historical patterns.
    """

    def __init__(
        self,
        seasonal_period: int = 7,
        auto_arima: bool = True
    ):
        """
        Initialize SARIMA forecaster

        Args:
            seasonal_period: Seasonal period (7 for weekly)
            auto_arima: Use auto-ARIMA for parameter selection
        """
        super().__init__(model_name="sarima")
        self.seasonal_period = seasonal_period
        self.use_auto_arima = auto_arima
        self.sarima_model: Optional[SARIMAX] = None
        self.sarima_result = None
        self.order: Optional[tuple] = None
        self.seasonal_order: Optional[tuple] = None

    def fit(
        self,
        train_data: pd.DataFrame,
        target_column: str = "y",
        date_column: str = "ds",
        exogenous_features: Optional[List[str]] = None,
        hyperparameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Train SARIMA model

        Args:
            train_data: Training data
            target_column: Target variable column
            date_column: Date column
            exogenous_features: IGNORED (SARIMA uses time-series only)
            hyperparameters: SARIMA order parameters

        Returns:
            Training metrics
        """
        # Validate data
        is_valid, error_msg = self.validate_data(train_data, target_column, date_column)
        if not is_valid:
            raise ValueError(f"Invalid training data: {error_msg}")

        # Check minimum data requirement
        if len(train_data) < 60:
            raise ValueError(
                f"SARIMA requires >= 60 data points (got {len(train_data)}). "
                f"Use Prophet or XGBoost for limited data."
            )

        # Extract time series
        y = train_data[target_column].values

        # Test stationarity
        ts_utils = TimeSeriesUtils()
        stationarity = ts_utils.test_stationarity(pd.Series(y))

        logger.info(
            f"Stationarity test: {stationarity.get('overall_conclusion', 'Unknown')} "
            f"(ADF p-value: {stationarity.get('adf_pvalue', 1.0):.4f})"
        )

        # Get recommended SARIMA order
        if self.use_auto_arima:
            sarima_recommendation = ts_utils.recommend_sarima_order(
                pd.Series(y),
                seasonal_period=self.seasonal_period
            )

            if not sarima_recommendation["is_suitable"]:
                raise ValueError(
                    f"SARIMA not suitable: {sarima_recommendation['reason']}"
                )

            self.order = sarima_recommendation["order"]
            self.seasonal_order = sarima_recommendation["seasonal_order"]

            logger.info(
                f"Auto-ARIMA selected order: {self.order}, "
                f"seasonal_order: {self.seasonal_order}"
            )
        else:
            # Use provided hyperparameters or defaults
            if hyperparameters:
                self.order = hyperparameters.get("order", (1, 1, 1))
                self.seasonal_order = hyperparameters.get(
                    "seasonal_order",
                    (1, 1, 1, self.seasonal_period)
                )
            else:
                # Default SARIMA(1,1,1)(1,1,1,7)
                self.order = (1, 1, 1)
                self.seasonal_order = (1, 1, 1, self.seasonal_period)

        # Fit SARIMAX model
        logger.info(f"Fitting SARIMA{self.order}{self.seasonal_order}")

        try:
            self.sarima_model = SARIMAX(
                y,
                order=self.order,
                seasonal_order=self.seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False
            )

            self.sarima_result = self.sarima_model.fit(disp=False)

            # Calculate in-sample metrics
            y_pred = self.sarima_result.fittedvalues
            metrics = self.calculate_metrics(y, y_pred)

            # Store metadata
            self.training_metadata = {
                "data_points": len(train_data),
                "order": self.order,
                "seasonal_order": self.seasonal_order,
                "stationarity": stationarity.get("overall_conclusion"),
                "aic": float(self.sarima_result.aic),
                "bic": float(self.sarima_result.bic),
                "metrics": metrics
            }

            self.is_fitted = True

            logger.info(
                f"SARIMA trained, MAPE: {metrics['mape']:.2f}%, "
                f"AIC: {self.sarima_result.aic:.2f}"
            )

            return metrics

        except Exception as e:
            logger.error(f"SARIMA training failed: {e}")
            raise ValueError(f"SARIMA training failed: {str(e)}")

    def predict(
        self,
        horizon: int,
        exogenous_future: Optional[pd.DataFrame] = None,
        return_confidence: bool = True
    ) -> pd.DataFrame:
        """
        Make predictions

        Args:
            horizon: Number of periods to forecast
            exogenous_future: IGNORED (SARIMA doesn't use external features)
            return_confidence: Whether to return confidence intervals

        Returns:
            DataFrame with predictions
        """
        if not self.is_fitted or self.sarima_result is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Make predictions
        forecast = self.sarima_result.get_forecast(steps=horizon)

        # Get prediction mean and confidence intervals
        y_pred = forecast.predicted_mean
        conf_int = forecast.conf_int(alpha=0.2)  # 80% confidence interval

        # Create result dataframe
        forecast_dates = pd.date_range(
            start=pd.Timestamp.now(),
            periods=horizon,
            freq="D"
        )

        result = pd.DataFrame({
            "ds": forecast_dates,
            "yhat": y_pred.values
        })

        if return_confidence:
            result["yhat_lower"] = conf_int.iloc[:, 0].values
            result["yhat_upper"] = conf_int.iloc[:, 1].values

        return result

    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """
        SARIMA doesn't use features, returns None

        Returns:
            None (SARIMA is pure time-series)
        """
        return None

    def serialize(self, filepath: str) -> bool:
        """
        Save model to disk

        Args:
            filepath: Path to save model (pickle format)

        Returns:
            True if successful
        """
        if not self.is_fitted or self.sarima_result is None:
            logger.error("Cannot serialize unfitted model")
            return False

        try:
            model_data = {
                "sarima_result": self.sarima_result,
                "order": self.order,
                "seasonal_order": self.seasonal_order,
                "seasonal_period": self.seasonal_period,
                "training_metadata": self.training_metadata
            }

            joblib.dump(model_data, filepath)
            logger.info(f"Saved SARIMA model to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to serialize SARIMA model: {e}")
            return False

    def deserialize(self, filepath: str) -> bool:
        """
        Load model from disk

        Args:
            filepath: Path to load model from

        Returns:
            True if successful
        """
        try:
            model_data = joblib.load(filepath)

            self.sarima_result = model_data["sarima_result"]
            self.order = model_data["order"]
            self.seasonal_order = model_data["seasonal_order"]
            self.seasonal_period = model_data["seasonal_period"]
            self.training_metadata = model_data.get("training_metadata", {})

            self.is_fitted = True

            logger.info(f"Loaded SARIMA model from {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to deserialize SARIMA model: {e}")
            return False

    def get_model_diagnostics(self) -> Dict[str, Any]:
        """
        Get model diagnostics (AIC, BIC, etc.)

        Returns:
            Diagnostic statistics
        """
        if not self.is_fitted or self.sarima_result is None:
            return {}

        return {
            "aic": float(self.sarima_result.aic),
            "bic": float(self.sarima_result.bic),
            "hqic": float(self.sarima_result.hqic),
            "llf": float(self.sarima_result.llf),  # Log-likelihood
            "order": self.order,
            "seasonal_order": self.seasonal_order
        }

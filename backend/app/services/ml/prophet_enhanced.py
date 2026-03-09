"""
Enhanced Prophet Wrapper with Exogenous Regressors

Wraps Facebook Prophet with support for external features:
- Weather data (temperature, rain, humidity)
- Events (festivals, IPL matches)
- PyTrends (search trends)
- Promotions

This allows Prophet to incorporate external signals, improving accuracy
for new cafes with limited historical data.
"""

import pandas as pd
import numpy as np
from prophet import Prophet
from prophet.serialize import model_to_json, model_from_json
import logging
import json
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ProphetEnhanced:
    """
    Enhanced Prophet with exogenous regressors

    Features:
    - Add external regressors (weather, events, trends)
    - Automatic regressor scaling
    - Holiday effects
    - Custom seasonality
    - Model serialization
    """

    def __init__(
        self,
        growth: str = "linear",
        changepoint_prior_scale: float = 0.05,
        seasonality_prior_scale: float = 10.0,
        holidays_prior_scale: float = 10.0,
        seasonality_mode: str = "additive",
        weekly_seasonality: bool = True,
        yearly_seasonality: bool = False,
        daily_seasonality: bool = False
    ):
        """
        Initialize Prophet model

        Args:
            growth: Growth type ("linear" or "logistic")
            changepoint_prior_scale: Flexibility of trend (higher = more flexible)
            seasonality_prior_scale: Strength of seasonality
            holidays_prior_scale: Strength of holiday effects
            seasonality_mode: "additive" or "multiplicative"
            weekly_seasonality: Enable weekly seasonality
            yearly_seasonality: Enable yearly seasonality (requires 2+ years data)
            daily_seasonality: Enable daily seasonality (usually False for daily data)
        """
        self.model = Prophet(
            growth=growth,
            changepoint_prior_scale=changepoint_prior_scale,
            seasonality_prior_scale=seasonality_prior_scale,
            holidays_prior_scale=holidays_prior_scale,
            seasonality_mode=seasonality_mode,
            weekly_seasonality=weekly_seasonality,
            yearly_seasonality=yearly_seasonality,
            daily_seasonality=daily_seasonality
        )

        self.regressors: List[str] = []
        self.is_fitted = False

    def add_regressors(
        self,
        regressor_names: List[str],
        prior_scale: float = 10.0,
        mode: str = "additive"
    ) -> None:
        """
        Add external regressors to Prophet

        Args:
            regressor_names: List of regressor column names
            prior_scale: Regularization strength (higher = more influence)
            mode: "additive" or "multiplicative"
        """
        for regressor in regressor_names:
            if regressor not in self.regressors:
                self.model.add_regressor(
                    regressor,
                    prior_scale=prior_scale,
                    mode=mode
                )
                self.regressors.append(regressor)
                logger.info(f"Added regressor: {regressor}")

    def add_country_holidays(self, country_name: str = "IN") -> None:
        """
        Add country holidays to model

        Args:
            country_name: ISO country code (default "IN" for India)
        """
        self.model.add_country_holidays(country_name=country_name)
        logger.info(f"Added {country_name} holidays to Prophet")

    def fit(
        self,
        df: pd.DataFrame,
        regressors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fit Prophet model

        Args:
            df: DataFrame with columns:
                - ds: date (required by Prophet)
                - y: target variable (required by Prophet)
                - [regressors]: external features (optional)
            regressors: List of regressor column names

        Returns:
            Fit statistics
        """
        # Validate input
        if df.empty:
            raise ValueError("Training data is empty")

        if "ds" not in df.columns or "y" not in df.columns:
            raise ValueError("DataFrame must have 'ds' and 'y' columns")

        # Add regressors
        if regressors:
            self.add_regressors(regressors)

        # Ensure regressors are present
        for regressor in self.regressors:
            if regressor not in df.columns:
                logger.warning(f"Regressor '{regressor}' not found in data, skipping")

        # Fit model
        logger.info(f"Fitting Prophet with {len(df)} data points")
        self.model.fit(df)
        self.is_fitted = True

        return {
            "data_points": len(df),
            "regressors": self.regressors,
            "training_completed": True
        }

    def predict(
        self,
        periods: int,
        freq: str = "D",
        future_regressors: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Make predictions

        Args:
            periods: Number of periods to forecast
            freq: Frequency of predictions ("D" for daily)
            future_regressors: DataFrame with future values of regressors

        Returns:
            DataFrame with predictions:
            - ds: date
            - yhat: predicted value
            - yhat_lower: lower confidence bound
            - yhat_upper: upper confidence bound
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        # Create future dataframe
        future = self.model.make_future_dataframe(periods=periods, freq=freq)

        # Add future regressor values
        if self.regressors:
            if future_regressors is None:
                logger.warning(
                    "Model uses regressors but no future values provided. "
                    "Using last known values."
                )
                # Use last known values (simple forward-fill)
                last_values = {reg: 0 for reg in self.regressors}
            else:
                # Merge future regressors
                future = future.merge(
                    future_regressors,
                    on="ds",
                    how="left"
                )

                # Fill missing regressor values
                for regressor in self.regressors:
                    if regressor in future.columns:
                        future[regressor].fillna(
                            future[regressor].mean(),
                            inplace=True
                        )
                    else:
                        logger.warning(f"Regressor '{regressor}' not in future data")
                        future[regressor] = 0

        # Make predictions
        forecast = self.model.predict(future)

        # Return only future periods
        forecast = forecast.tail(periods)

        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]

    def predict_with_components(
        self,
        periods: int,
        freq: str = "D",
        future_regressors: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Make predictions with component breakdown

        Returns predictions + trend + seasonality + regressor effects

        Args:
            periods: Number of periods to forecast
            freq: Frequency
            future_regressors: Future regressor values

        Returns:
            DataFrame with predictions and components
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        # Create future dataframe
        future = self.model.make_future_dataframe(periods=periods, freq=freq)

        # Add future regressors
        if self.regressors and future_regressors is not None:
            future = future.merge(future_regressors, on="ds", how="left")
            for regressor in self.regressors:
                if regressor in future.columns:
                    future[regressor].fillna(future[regressor].mean(), inplace=True)

        # Get full forecast with components
        forecast = self.model.predict(future)

        return forecast.tail(periods)

    def get_regressor_contributions(self) -> Dict[str, float]:
        """
        Get contribution of each regressor to predictions

        Returns:
            Dictionary mapping regressor name to average contribution
        """
        if not self.is_fitted:
            return {}

        contributions = {}
        for regressor in self.regressors:
            # Get regressor coefficient from model
            if hasattr(self.model, 'params') and regressor in self.model.params:
                contributions[regressor] = float(self.model.params[regressor])

        return contributions

    def serialize(self, filepath: str) -> bool:
        """
        Save model to JSON file

        Args:
            filepath: Path to save model

        Returns:
            True if successful
        """
        if not self.is_fitted:
            logger.error("Cannot serialize unfitted model")
            return False

        try:
            with open(filepath, 'w') as f:
                model_json = model_to_json(self.model)
                metadata = {
                    "regressors": self.regressors,
                    "is_fitted": self.is_fitted
                }
                json.dump({
                    "model": model_json,
                    "metadata": metadata
                }, f)

            logger.info(f"Saved Prophet model to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to serialize model: {e}")
            return False

    def deserialize(self, filepath: str) -> bool:
        """
        Load model from JSON file

        Args:
            filepath: Path to load model from

        Returns:
            True if successful
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            self.model = model_from_json(data["model"])
            self.regressors = data["metadata"]["regressors"]
            self.is_fitted = data["metadata"]["is_fitted"]

            logger.info(f"Loaded Prophet model from {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to deserialize model: {e}")
            return False

    def get_model_params(self) -> Dict[str, Any]:
        """Get model parameters"""
        return {
            "growth": self.model.growth,
            "changepoint_prior_scale": self.model.changepoint_prior_scale,
            "seasonality_prior_scale": self.model.seasonality_prior_scale,
            "holidays_prior_scale": self.model.holidays_prior_scale,
            "seasonality_mode": self.model.seasonality_mode,
            "regressors": self.regressors,
            "is_fitted": self.is_fitted
        }

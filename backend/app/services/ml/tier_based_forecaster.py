"""
Tier-Based Forecaster

Automatically selects forecasting strategy based on data availability.
Critical for new QSRs and small cafes with limited historical data.

Tiers:
- Tier 1 (<14 days): Category baseline + external trends
- Tier 2 (14-30 days): Lightweight Prophet + heavy external data
- Tier 3 (30-60 days): Prophet + XGBoost (skip SARIMA)
- Tier 4 (60-90 days): Full ensemble (Prophet + SARIMA + XGBoost)
- Tier 5 (>90 days): Advanced techniques
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.services.ml.models import ProphetForecaster, SARIMAForecaster, XGBoostForecaster
from app.services.ml.ensemble_predictor import EnsemblePredictor
from app.services.data_quality import DataTierClassifier, get_data_tier_classifier

logger = logging.getLogger(__name__)


class TierBasedForecaster:
    """
    Intelligent forecaster that adapts to data availability

    Automatically:
    - Classifies cafe by data tier
    - Selects appropriate models
    - Adjusts hyperparameters
    - Sets realistic MAPE targets
    """

    def __init__(self):
        self.tier_classifier = get_data_tier_classifier()
        self.current_tier: Optional[str] = None
        self.days_of_data: int = 0

    def forecast(
        self,
        train_data: pd.DataFrame,
        horizon: int,
        exogenous_future: Optional[pd.DataFrame] = None,
        target_column: str = "y",
        date_column: str = "ds",
        exogenous_features: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Make forecast using tier-appropriate strategy

        Args:
            train_data: Historical training data
            horizon: Number of periods to forecast
            exogenous_future: Future feature values
            target_column: Target variable column
            date_column: Date column
            exogenous_features: External features

        Returns:
            Forecast results with predictions and metadata
        """
        # Classify data tier
        self.days_of_data = len(train_data)
        tier = self.tier_classifier.classify_by_days(self.days_of_data)
        self.current_tier = tier.value

        strategy = self.tier_classifier.get_forecasting_strategy(tier)

        logger.info(
            f"Classified as {tier.value}: {self.days_of_data} days of data. "
            f"Strategy: {strategy['method']}"
        )

        # Select forecasting method based on tier
        if tier.value == "tier_1":
            return self._tier1_forecast(
                train_data, horizon, exogenous_future, strategy
            )

        elif tier.value == "tier_2":
            return self._tier2_forecast(
                train_data, horizon, exogenous_future,
                target_column, date_column, exogenous_features, strategy
            )

        elif tier.value == "tier_3":
            return self._tier3_forecast(
                train_data, horizon, exogenous_future,
                target_column, date_column, exogenous_features, strategy
            )

        else:  # tier_4 or tier_5
            return self._tier4_forecast(
                train_data, horizon, exogenous_future,
                target_column, date_column, exogenous_features, strategy
            )

    def _tier1_forecast(
        self,
        train_data: pd.DataFrame,
        horizon: int,
        exogenous_future: Optional[pd.DataFrame],
        strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Tier 1: <14 days - Category baseline + external trends

        With <14 days, ML models are unreliable. Use:
        - Category average (similar cafes)
        - Heavy external data weighting (70%)
        - Manual adjustment recommended
        """
        logger.warning(
            f"Only {self.days_of_data} days of data (Tier 1). "
            "Using category baseline. Accuracy will be limited (MAPE ~30%)."
        )

        # Simple baseline: average of recent data
        baseline_avg = train_data["y"].mean()

        # Apply external data adjustments (simplified)
        external_adjustment = 1.0  # Default no adjustment

        if exogenous_future is not None and "restaurant_search_trend" in exogenous_future.columns:
            # Use PyTrends as proxy for market conditions
            trend_avg = exogenous_future["restaurant_search_trend"].mean()
            # Normalize (assume 50 is neutral)
            external_adjustment = 1.0 + ((trend_avg - 50) / 100)

        # Generate predictions
        predictions = [baseline_avg * external_adjustment] * horizon

        # Create result
        dates = pd.date_range(
            start=pd.Timestamp.now(),
            periods=horizon,
            freq="D"
        )

        result_df = pd.DataFrame({
            "ds": dates,
            "yhat": predictions,
            "yhat_lower": [p * 0.7 for p in predictions],  # Wide interval
            "yhat_upper": [p * 1.3 for p in predictions]
        })

        return {
            "predictions": result_df,
            "method": "category_baseline",
            "tier": "tier_1",
            "days_of_data": self.days_of_data,
            "expected_mape": strategy["target_mape"],
            "confidence": "low",
            "recommendations": strategy["recommendations"]
        }

    def _tier2_forecast(
        self,
        train_data: pd.DataFrame,
        horizon: int,
        exogenous_future: Optional[pd.DataFrame],
        target_column: str,
        date_column: str,
        exogenous_features: Optional[List[str]],
        strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Tier 2: 14-30 days - Lightweight Prophet + heavy external data

        With 14-30 days:
        - Prophet with weekly seasonality only
        - Heavy external data weighting (60%)
        - Conservative hyperparameters
        """
        logger.info(f"Using Tier 2 strategy: Lightweight Prophet ({self.days_of_data} days)")

        # Initialize Prophet with conservative settings
        prophet = ProphetForecaster(data_tier="tier_2")

        # Train
        prophet.fit(
            train_data=train_data,
            target_column=target_column,
            date_column=date_column,
            exogenous_features=exogenous_features
        )

        # Predict
        predictions = prophet.predict(
            horizon=horizon,
            exogenous_future=exogenous_future,
            return_confidence=True
        )

        return {
            "predictions": predictions,
            "method": "lightweight_prophet",
            "tier": "tier_2",
            "days_of_data": self.days_of_data,
            "models_used": ["prophet"],
            "expected_mape": strategy["target_mape"],
            "confidence": "medium",
            "recommendations": strategy["recommendations"]
        }

    def _tier3_forecast(
        self,
        train_data: pd.DataFrame,
        horizon: int,
        exogenous_future: Optional[pd.DataFrame],
        target_column: str,
        date_column: str,
        exogenous_features: Optional[List[str]],
        strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Tier 3: 30-60 days - Prophet + XGBoost (skip SARIMA)

        With 30-60 days:
        - Prophet with moderate settings
        - XGBoost with full features
        - Skip SARIMA (needs 60+ days)
        - Ensemble: Prophet 25% + XGBoost 50% + External 25%
        """
        logger.info(f"Using Tier 3 strategy: Prophet + XGBoost ({self.days_of_data} days)")

        # Initialize models
        prophet = ProphetForecaster(data_tier="tier_3")
        xgboost = XGBoostForecaster()

        # Train models
        prophet.fit(
            train_data=train_data,
            target_column=target_column,
            date_column=date_column,
            exogenous_features=exogenous_features
        )

        xgboost.fit(
            train_data=train_data,
            target_column=target_column,
            date_column=date_column,
            exogenous_features=exogenous_features
        )

        # Create ensemble
        ensemble = EnsemblePredictor(weighting_strategy="accuracy")
        ensemble.add_model(prophet)
        ensemble.add_model(xgboost)

        # Calculate weights (Prophet 25%, XGBoost 50%, external buffer 25%)
        ensemble.weights = {"prophet": 0.40, "xgboost": 0.60}

        # Predict
        predictions = ensemble.predict(
            horizon=horizon,
            exogenous_future=exogenous_future,
            return_components=True
        )

        return {
            "predictions": predictions,
            "method": "limited_ensemble",
            "tier": "tier_3",
            "days_of_data": self.days_of_data,
            "models_used": ["prophet", "xgboost"],
            "weights": ensemble.weights,
            "expected_mape": strategy["target_mape"],
            "confidence": "medium-high",
            "recommendations": strategy["recommendations"]
        }

    def _tier4_forecast(
        self,
        train_data: pd.DataFrame,
        horizon: int,
        exogenous_future: Optional[pd.DataFrame],
        target_column: str,
        date_column: str,
        exogenous_features: Optional[List[str]],
        strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Tier 4: 60+ days - Full ensemble (Prophet + SARIMA + XGBoost)

        With 60+ days:
        - All three models
        - Full hyperparameter tuning
        - Weighted by accuracy
        - Target MAPE: 10-15%
        """
        logger.info(f"Using Tier 4 strategy: Full ensemble ({self.days_of_data} days)")

        # Initialize all models
        prophet = ProphetForecaster(data_tier="tier_4")
        xgboost = XGBoostForecaster()

        # Train Prophet and XGBoost
        prophet.fit(
            train_data=train_data,
            target_column=target_column,
            date_column=date_column,
            exogenous_features=exogenous_features
        )

        xgboost.fit(
            train_data=train_data,
            target_column=target_column,
            date_column=date_column,
            exogenous_features=exogenous_features
        )

        # Try SARIMA (may fail if data not stationary)
        sarima = None
        try:
            sarima = SARIMAForecaster(seasonal_period=7, auto_arima=True)
            sarima.fit(
                train_data=train_data,
                target_column=target_column,
                date_column=date_column
            )
            logger.info("SARIMA successfully trained")
        except Exception as e:
            logger.warning(f"SARIMA training failed: {e}. Using Prophet + XGBoost only.")

        # Create ensemble
        ensemble = EnsemblePredictor(weighting_strategy="accuracy")
        ensemble.add_model(prophet)
        ensemble.add_model(xgboost)

        if sarima and sarima.is_fitted:
            ensemble.add_model(sarima)
            # Default weights: Prophet 30%, SARIMA 25%, XGBoost 45%
            ensemble.weights = {"prophet": 0.30, "sarima": 0.25, "xgboost": 0.45}
            models_used = ["prophet", "sarima", "xgboost"]
        else:
            # Without SARIMA: Prophet 35%, XGBoost 65%
            ensemble.weights = {"prophet": 0.35, "xgboost": 0.65}
            models_used = ["prophet", "xgboost"]

        # Predict
        predictions = ensemble.predict(
            horizon=horizon,
            exogenous_future=exogenous_future,
            return_components=True
        )

        return {
            "predictions": predictions,
            "method": "full_ensemble",
            "tier": "tier_4",
            "days_of_data": self.days_of_data,
            "models_used": models_used,
            "weights": ensemble.weights,
            "expected_mape": strategy["target_mape"],
            "confidence": "high",
            "recommendations": strategy["recommendations"]
        }

    def get_tier_info(self) -> Dict[str, Any]:
        """
        Get information about current data tier

        Returns:
            Tier information and recommendations
        """
        if self.current_tier is None:
            return {"error": "No forecast made yet"}

        from app.services.data_quality import DataTier

        tier_enum = DataTier(self.current_tier)
        return self.tier_classifier.get_tier_info(tier_enum)

    def assess_readiness(
        self,
        days_of_data: int,
        data_quality_score: float = 1.0
    ) -> Dict[str, Any]:
        """
        Assess cafe's readiness for ML forecasting

        Args:
            days_of_data: Days of historical data
            data_quality_score: Data quality score (0-1)

        Returns:
            Readiness assessment
        """
        return self.tier_classifier.assess_cafe_readiness(
            days_of_data=days_of_data,
            data_quality_score=data_quality_score
        )

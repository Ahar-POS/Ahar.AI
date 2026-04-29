"""
Data Tier Classifier

Classifies cafe/restaurant by data availability and selects appropriate forecasting strategy.

Critical for new QSRs and small cafes:
- Most new cafes have <90 days of data (cold start problem)
- Traditional time-series models (SARIMA, Prophet) need 60+ days
- New cafes must rely heavily on external signals (PyTrends, weather, events)

Tiers:
- Tier 1 (<14 days): Category baseline + external trends only
- Tier 2 (14-30 days): Lightweight Prophet + heavy external data
- Tier 3 (30-60 days): Prophet + XGBoost (skip SARIMA)
- Tier 4 (60-90 days): Full ensemble (Prophet + SARIMA + XGBoost)
- Tier 5 (>90 days): Advanced techniques (deep learning, causal inference)
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from app.utils.timezone import now_ist
from enum import Enum

logger = logging.getLogger(__name__)


class DataTier(str, Enum):
    """Data availability tiers"""
    TIER_1 = "tier_1"  # <14 days
    TIER_2 = "tier_2"  # 14-30 days
    TIER_3 = "tier_3"  # 30-60 days
    TIER_4 = "tier_4"  # 60-90 days
    TIER_5 = "tier_5"  # >90 days


class DataTierClassifier:
    """
    Classifies restaurant/cafe by data availability

    Used to select appropriate forecasting strategy:
    - Limited data → Rely on external signals (PyTrends, weather, events)
    - Sufficient data → Use full ensemble (Prophet + SARIMA + XGBoost)
    """

    def __init__(self):
        # Tier thresholds (days of historical data)
        self.tier_thresholds = {
            DataTier.TIER_1: (0, 14),
            DataTier.TIER_2: (14, 30),
            DataTier.TIER_3: (30, 60),
            DataTier.TIER_4: (60, 90),
            DataTier.TIER_5: (90, float('inf'))
        }

    def classify_by_days(self, days_of_data: int) -> DataTier:
        """
        Classify tier based on number of days of historical data

        Args:
            days_of_data: Number of days of historical data available

        Returns:
            DataTier enum
        """
        for tier, (min_days, max_days) in self.tier_thresholds.items():
            if min_days <= days_of_data < max_days:
                logger.info(
                    f"Classified as {tier.value}: {days_of_data} days of data"
                )
                return tier

        # Fallback to Tier 5 if > 90 days
        return DataTier.TIER_5

    def get_forecasting_strategy(self, tier: DataTier) -> Dict[str, Any]:
        """
        Get recommended forecasting strategy for a tier

        Args:
            tier: Data tier

        Returns:
            Strategy configuration:
            {
                "method": "strategy_name",
                "models": ["prophet", "xgboost"],
                "external_data_weight": 0.6,  # 60% weight on external signals
                "target_mape": 18.0,
                "description": "...",
                "recommendations": ["..."]
            }
        """
        strategies = {
            DataTier.TIER_1: {
                "method": "category_baseline",
                "models": ["category_baseline"],
                "external_data_weight": 0.70,  # Heavy reliance on external data
                "target_mape": 30.0,
                "min_mape": 25.0,
                "max_mape": 35.0,
                "description": (
                    "Insufficient data for ML models. Use category averages "
                    "(similar cafes) adjusted by external signals."
                ),
                "recommendations": [
                    "Focus on collecting data (target: 14+ days)",
                    "Rely heavily on PyTrends (60% weight)",
                    "Use weather forecasts (20% weight)",
                    "Monitor local events (20% weight)",
                    "Manual adjustments recommended",
                    "Review forecast accuracy weekly"
                ]
            },
            DataTier.TIER_2: {
                "method": "lightweight_prophet",
                "models": ["prophet"],
                "external_data_weight": 0.60,  # Moderate reliance
                "target_mape": 22.0,
                "min_mape": 18.0,
                "max_mape": 25.0,
                "description": (
                    "Minimal data for Prophet. Use simple Prophet (weekly seasonality only) "
                    "with heavy external data weighting."
                ),
                "recommendations": [
                    "Prophet: 30% weight (weekly patterns only)",
                    "PyTrends: 40% weight (market signals)",
                    "Weather: 20% weight",
                    "Events: 10% weight",
                    "Disable daily/yearly seasonality",
                    "Collect 30+ days for better accuracy"
                ]
            },
            DataTier.TIER_3: {
                "method": "limited_ensemble",
                "models": ["prophet", "xgboost"],
                "external_data_weight": 0.40,  # Balanced
                "target_mape": 18.0,
                "min_mape": 15.0,
                "max_mape": 20.0,
                "description": (
                    "Moderate data. Use Prophet + XGBoost ensemble. "
                    "Skip SARIMA (needs 60+ days for stationarity testing)."
                ),
                "recommendations": [
                    "Prophet: 25% weight (with weather regressors)",
                    "XGBoost: 50% weight (uses all features)",
                    "PyTrends: 25% effective weight via XGBoost",
                    "Enable weekly seasonality",
                    "Use all external features in XGBoost",
                    "Collect 60+ days for full ensemble"
                ]
            },
            DataTier.TIER_4: {
                "method": "full_ensemble",
                "models": ["prophet", "sarima", "xgboost"],
                "external_data_weight": 0.25,  # Lower reliance
                "target_mape": 12.0,
                "min_mape": 10.0,
                "max_mape": 15.0,
                "description": (
                    "Sufficient data for full ensemble. "
                    "Use Prophet + SARIMA + XGBoost with optimal weighting."
                ),
                "recommendations": [
                    "Prophet: 30% weight (with all seasonality)",
                    "SARIMA: 25% weight (if stationary)",
                    "XGBoost: 45% weight (all features)",
                    "Enable all seasonality patterns",
                    "Use exogenous regressors in Prophet",
                    "Consider hyperparameter tuning",
                    "This is the TARGET tier for accuracy"
                ]
            },
            DataTier.TIER_5: {
                "method": "advanced_ensemble",
                "models": ["prophet", "sarima", "xgboost", "lstm"],
                "external_data_weight": 0.15,  # Low reliance
                "target_mape": 10.0,
                "min_mape": 8.0,
                "max_mape": 12.0,
                "description": (
                    "Abundant data. Use advanced techniques: "
                    "LSTM, N-BEATS, causal inference, stacking."
                ),
                "recommendations": [
                    "Enable deep learning models (LSTM, N-BEATS)",
                    "Use stacking (meta-model learns to combine)",
                    "Implement causal inference (DAGs)",
                    "Per-item hyperparameter tuning",
                    "Advanced feature engineering",
                    "Experiment with probabilistic forecasting",
                    "Target industry-best MAPE (<10%)"
                ]
            }
        }

        return strategies.get(tier, strategies[DataTier.TIER_4])

    def get_tier_info(self, tier: DataTier) -> Dict[str, Any]:
        """
        Get detailed information about a tier

        Args:
            tier: Data tier

        Returns:
            Tier information and characteristics
        """
        strategy = self.get_forecasting_strategy(tier)
        min_days, max_days = self.tier_thresholds[tier]

        return {
            "tier": tier.value,
            "name": tier.name,
            "min_days": min_days,
            "max_days": max_days if max_days != float('inf') else None,
            "strategy": strategy,
            "characteristics": self._get_tier_characteristics(tier)
        }

    def _get_tier_characteristics(self, tier: DataTier) -> List[str]:
        """Get characteristics/challenges of each tier"""
        characteristics = {
            DataTier.TIER_1: [
                "Very new cafe/restaurant (<2 weeks open)",
                "Insufficient data for ML models",
                "High uncertainty in predictions",
                "Rely on category averages",
                "Manual adjustments critical",
                "Focus on data collection"
            ],
            DataTier.TIER_2: [
                "New cafe (2-4 weeks open)",
                "Barely enough for Prophet",
                "Weekly patterns emerging",
                "Heavy reliance on external signals",
                "Limited model validation possible",
                "Accuracy improving weekly"
            ],
            DataTier.TIER_3: [
                "Growing cafe (1-2 months open)",
                "Patterns becoming clearer",
                "Can use ensemble methods",
                "Balanced internal/external data",
                "Seasonality not yet reliable",
                "Approaching production-ready accuracy"
            ],
            DataTier.TIER_4: [
                "Established cafe (2-3 months open)",
                "Strong historical patterns",
                "Full ensemble available",
                "Reliable weekly seasonality",
                "Target accuracy achievable",
                "Production-ready forecasting"
            ],
            DataTier.TIER_5: [
                "Mature restaurant (3+ months open)",
                "Rich historical data",
                "Advanced techniques viable",
                "Multiple seasonality patterns",
                "Industry-best accuracy possible",
                "Consider deep learning models"
            ]
        }

        return characteristics.get(tier, [])

    def get_upgrade_recommendations(
        self,
        current_tier: DataTier,
        days_until_upgrade: int
    ) -> Dict[str, Any]:
        """
        Get recommendations for upgrading to next tier

        Args:
            current_tier: Current data tier
            days_until_upgrade: Days until enough data for next tier

        Returns:
            Upgrade information and recommendations
        """
        tier_order = [
            DataTier.TIER_1,
            DataTier.TIER_2,
            DataTier.TIER_3,
            DataTier.TIER_4,
            DataTier.TIER_5
        ]

        current_idx = tier_order.index(current_tier)

        if current_idx >= len(tier_order) - 1:
            return {
                "can_upgrade": False,
                "message": "Already at highest tier",
                "next_tier": None
            }

        next_tier = tier_order[current_idx + 1]
        next_strategy = self.get_forecasting_strategy(next_tier)

        return {
            "can_upgrade": True,
            "current_tier": current_tier.value,
            "next_tier": next_tier.value,
            "days_until_upgrade": days_until_upgrade,
            "upgrade_date": (
                now_ist() + timedelta(days=days_until_upgrade)
            ).strftime("%Y-%m-%d"),
            "expected_mape_improvement": abs(
                self.get_forecasting_strategy(current_tier)["target_mape"]
                - next_strategy["target_mape"]
            ),
            "new_features": [
                f"Enable {model}" for model in next_strategy["models"]
                if model not in self.get_forecasting_strategy(current_tier)["models"]
            ],
            "recommendations": next_strategy["recommendations"][:3]
        }

    def assess_cafe_readiness(
        self,
        days_of_data: int,
        data_quality_score: float = 1.0
    ) -> Dict[str, Any]:
        """
        Assess cafe's readiness for ML forecasting

        Args:
            days_of_data: Days of historical data
            data_quality_score: Data quality score (0-1, default 1.0)

        Returns:
            Readiness assessment
        """
        tier = self.classify_by_days(days_of_data)
        strategy = self.get_forecasting_strategy(tier)

        # Calculate readiness score (0-100)
        if tier == DataTier.TIER_1:
            readiness_score = min(50, (days_of_data / 14) * 50)
            readiness_level = "not_ready"
        elif tier == DataTier.TIER_2:
            readiness_score = 50 + (days_of_data - 14) / 16 * 20
            readiness_level = "marginal"
        elif tier == DataTier.TIER_3:
            readiness_score = 70 + (days_of_data - 30) / 30 * 15
            readiness_level = "ready"
        else:  # TIER_4 or TIER_5
            readiness_score = 85 + min(15, (days_of_data - 60) / 30 * 15)
            readiness_level = "production_ready"

        # Adjust for data quality
        readiness_score = readiness_score * data_quality_score

        return {
            "readiness_score": round(readiness_score, 1),
            "readiness_level": readiness_level,
            "tier": tier.value,
            "days_of_data": days_of_data,
            "data_quality_score": data_quality_score,
            "can_use_ml": tier.value >= DataTier.TIER_2.value,
            "recommended_strategy": strategy["method"],
            "expected_mape": strategy["target_mape"],
            "limitations": self._get_tier_characteristics(tier)[:3]
        }


# Singleton instance
_data_tier_classifier: Optional[DataTierClassifier] = None


def get_data_tier_classifier() -> DataTierClassifier:
    """Get singleton data tier classifier instance"""
    global _data_tier_classifier
    if _data_tier_classifier is None:
        _data_tier_classifier = DataTierClassifier()
    return _data_tier_classifier

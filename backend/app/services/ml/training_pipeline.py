"""
ML Training Pipeline

Orchestrates the complete model training workflow:
1. Load and validate data
2. Feature engineering
3. Outlier detection
4. Train individual models (Prophet, SARIMA, XGBoost)
5. Ensemble creation and weight optimization
6. Model evaluation and storage
7. Generate training reports

Supports both manual and scheduled training.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from app.utils.timezone import now_ist
from pathlib import Path

from app.services.ml.models import ProphetForecaster, SARIMAForecaster, XGBoostForecaster
from app.services.ml.ensemble_predictor import EnsemblePredictor
from app.services.ml.tier_based_forecaster import TierBasedForecaster
from app.services.ml.model_registry import get_model_registry
from app.services.data_quality import get_outlier_detector, get_confidence_calibrator
from app.services.feature_engineering import FeatureEngineeringService
from app.core.database import get_database

logger = logging.getLogger(__name__)


class TrainingPipeline:
    """
    Complete ML training pipeline

    Handles:
    - Data loading and validation
    - Feature engineering with temporal alignment
    - Outlier detection and removal
    - Model training (Prophet, SARIMA, XGBoost)
    - Ensemble creation and optimization
    - Model storage and versioning
    - Training reports
    """

    def __init__(
        self,
        ingredient_id: str,
        ingredient_name: str,
        lookback_days: int = 90,
        remove_outliers: bool = True
    ):
        """
        Initialize training pipeline

        Args:
            ingredient_id: Ingredient ID to train for
            ingredient_name: Ingredient name
            lookback_days: Days of historical data to use
            remove_outliers: Whether to remove outliers before training
        """
        self.ingredient_id = ingredient_id
        self.ingredient_name = ingredient_name
        self.lookback_days = lookback_days
        self.remove_outliers = remove_outliers

        self.db = get_database()
        self.model_registry = get_model_registry()
        self.feature_service = FeatureEngineeringService(self.db)
        self.outlier_detector = get_outlier_detector()

        self.training_data: Optional[pd.DataFrame] = None
        self.clean_data: Optional[pd.DataFrame] = None
        self.days_of_data: int = 0
        self.data_tier: Optional[str] = None

    async def run(
        self,
        validate_only: bool = False,
        hyperparameter_tuning: bool = False
    ) -> Dict[str, Any]:
        """
        Run complete training pipeline

        Args:
            validate_only: If True, only validate data without training
            hyperparameter_tuning: If True, run hyperparameter optimization

        Returns:
            Training results with metrics and model info
        """
        logger.info(
            f"Starting training pipeline for {self.ingredient_name} "
            f"(lookback: {self.lookback_days} days)"
        )

        pipeline_start = now_ist()

        try:
            # Step 1: Load and prepare data
            logger.info("Step 1/7: Loading data...")
            data_status = await self._load_and_prepare_data()

            if not data_status["success"]:
                return {
                    "success": False,
                    "error": data_status["error"],
                    "step": "data_loading"
                }

            if validate_only:
                return {
                    "success": True,
                    "validation_only": True,
                    "data_status": data_status
                }

            # Step 2: Feature engineering
            logger.info("Step 2/7: Feature engineering...")
            features_status = await self._engineer_features()

            if not features_status["success"]:
                return {
                    "success": False,
                    "error": features_status["error"],
                    "step": "feature_engineering"
                }

            # Step 3: Outlier detection
            logger.info("Step 3/7: Outlier detection...")
            outlier_status = self._detect_and_handle_outliers()

            # Step 4: Determine training strategy
            logger.info("Step 4/7: Determining training strategy...")
            strategy = self._determine_strategy()

            # Step 5: Train models
            logger.info(f"Step 5/7: Training models ({strategy['method']})...")
            training_results = await self._train_models(
                strategy=strategy,
                hyperparameter_tuning=hyperparameter_tuning
            )

            if not training_results["success"]:
                return {
                    "success": False,
                    "error": training_results["error"],
                    "step": "model_training"
                }

            # Step 6: Store models
            logger.info("Step 6/7: Storing models...")
            storage_status = await self._store_models(training_results["models"])

            # Step 7: Generate report
            logger.info("Step 7/7: Generating training report...")
            report = self._generate_report(
                data_status=data_status,
                features_status=features_status,
                outlier_status=outlier_status,
                strategy=strategy,
                training_results=training_results,
                storage_status=storage_status
            )

            pipeline_duration = (now_ist() - pipeline_start).total_seconds()
            report["pipeline_duration_seconds"] = round(pipeline_duration, 2)

            logger.info(
                f"✓ Training pipeline completed in {pipeline_duration:.1f}s. "
                f"Best MAPE: {report.get('best_mape', 'N/A')}%"
            )

            return report

        except Exception as e:
            logger.error(f"Training pipeline failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "step": "unknown"
            }

    async def _load_and_prepare_data(self) -> Dict[str, Any]:
        """Load historical data from database"""
        try:
            # Calculate date range
            end_date = now_ist()
            start_date = end_date - timedelta(days=self.lookback_days)

            # Load orders data
            orders = await self.feature_service.load_orders_data(
                start_date=start_date,
                end_date=end_date
            )

            if orders.empty:
                return {
                    "success": False,
                    "error": f"No order data found for ingredient {self.ingredient_id}"
                }

            # Filter for this ingredient
            # TODO: Add ingredient filtering based on your schema
            # For now, assuming 'y' column exists

            self.training_data = orders
            self.days_of_data = len(orders)

            # Classify data tier
            from app.services.data_quality import get_data_tier_classifier
            tier_classifier = get_data_tier_classifier()
            tier = tier_classifier.classify_by_days(self.days_of_data)
            self.data_tier = tier.value

            return {
                "success": True,
                "rows": len(orders),
                "days_of_data": self.days_of_data,
                "date_range": {
                    "start": orders["order_date"].min().strftime("%Y-%m-%d"),
                    "end": orders["order_date"].max().strftime("%Y-%m-%d")
                },
                "data_tier": self.data_tier
            }

        except Exception as e:
            logger.error(f"Data loading failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _engineer_features(self) -> Dict[str, Any]:
        """Engineer features with temporal alignment"""
        try:
            # Build ML features (training mode)
            features_df = await self.feature_service.build_ml_features(
                start_date=self.training_data["order_date"].min(),
                end_date=self.training_data["order_date"].max(),
                include_lags=True
            )

            if features_df.empty:
                return {
                    "success": False,
                    "error": "Feature engineering produced no features"
                }

            # Ensure required columns
            if "ds" not in features_df.columns:
                features_df["ds"] = features_df["order_date"]

            if "y" not in features_df.columns:
                # TODO: Map ingredient consumption to 'y' column
                # For now, using a placeholder
                features_df["y"] = features_df.get("quantity", 0)

            self.training_data = features_df

            return {
                "success": True,
                "features_count": len(features_df.columns),
                "feature_names": list(features_df.columns)[:20]  # First 20
            }

        except Exception as e:
            logger.error(f"Feature engineering failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _detect_and_handle_outliers(self) -> Dict[str, Any]:
        """Detect and optionally remove outliers"""
        try:
            # Detect outliers
            data_with_outliers = self.outlier_detector.detect_outliers(
                data=self.training_data,
                value_column="y",
                date_column="ds"
            )

            outlier_summary = self.outlier_detector.get_outlier_summary(
                data=self.training_data,
                value_column="y",
                date_column="ds"
            )

            if self.remove_outliers and outlier_summary["outlier_count"] > 0:
                # Remove outliers
                self.clean_data, outliers = self.outlier_detector.remove_outliers(
                    data=self.training_data,
                    value_column="y"
                )

                logger.info(
                    f"Removed {len(outliers)} outliers "
                    f"({outlier_summary['outlier_percentage']:.1f}%)"
                )
            else:
                self.clean_data = self.training_data

            return {
                "success": True,
                "outliers_detected": outlier_summary["outlier_count"],
                "outliers_removed": len(outliers) if self.remove_outliers else 0,
                "outlier_percentage": outlier_summary["outlier_percentage"]
            }

        except Exception as e:
            logger.warning(f"Outlier detection failed: {e}")
            self.clean_data = self.training_data
            return {
                "success": True,
                "outliers_detected": 0,
                "warning": str(e)
            }

    def _determine_strategy(self) -> Dict[str, Any]:
        """Determine training strategy based on data tier"""
        from app.services.data_quality import DataTier, get_data_tier_classifier

        tier_classifier = get_data_tier_classifier()
        tier = DataTier(self.data_tier)
        strategy = tier_classifier.get_forecasting_strategy(tier)

        return strategy

    async def _train_models(
        self,
        strategy: Dict[str, Any],
        hyperparameter_tuning: bool = False
    ) -> Dict[str, Any]:
        """Train models based on strategy"""
        try:
            models_trained = []
            training_metrics = {}

            # Prepare data
            train_df = self.clean_data.copy()

            # Get exogenous features (all except ds, y, _id, order_date)
            exogenous_features = [
                col for col in train_df.columns
                if col not in ["ds", "y", "_id", "order_date"]
            ]

            # Train based on strategy
            models_to_train = strategy.get("models", ["prophet"])

            # Prophet
            if "prophet" in models_to_train:
                logger.info("Training Prophet...")
                prophet = ProphetForecaster(data_tier=self.data_tier)

                prophet_metrics = prophet.fit(
                    train_data=train_df,
                    target_column="y",
                    date_column="ds",
                    exogenous_features=exogenous_features[:10]  # Limit to top 10 features
                )

                models_trained.append(("prophet", prophet))
                training_metrics["prophet"] = prophet_metrics
                logger.info(f"Prophet trained: MAPE {prophet_metrics['mape']:.2f}%")

            # SARIMA (only if in strategy)
            if "sarima" in models_to_train:
                logger.info("Training SARIMA...")
                try:
                    sarima = SARIMAForecaster(seasonal_period=7, auto_arima=True)

                    sarima_metrics = sarima.fit(
                        train_data=train_df,
                        target_column="y",
                        date_column="ds"
                    )

                    models_trained.append(("sarima", sarima))
                    training_metrics["sarima"] = sarima_metrics
                    logger.info(f"SARIMA trained: MAPE {sarima_metrics['mape']:.2f}%")

                except Exception as e:
                    logger.warning(f"SARIMA training failed: {e}")

            # XGBoost
            if "xgboost" in models_to_train:
                logger.info("Training XGBoost...")
                xgboost = XGBoostForecaster()

                xgboost_metrics = xgboost.fit(
                    train_data=train_df,
                    target_column="y",
                    date_column="ds",
                    exogenous_features=exogenous_features
                )

                models_trained.append(("xgboost", xgboost))
                training_metrics["xgboost"] = xgboost_metrics
                logger.info(f"XGBoost trained: MAPE {xgboost_metrics['mape']:.2f}%")

            if not models_trained:
                return {
                    "success": False,
                    "error": "No models successfully trained"
                }

            return {
                "success": True,
                "models": models_trained,
                "metrics": training_metrics,
                "strategy": strategy["method"]
            }

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _store_models(
        self,
        models: List[Tuple[str, Any]]
    ) -> Dict[str, Any]:
        """Store trained models in registry"""
        try:
            stored_models = []

            for model_type, model in models:
                # Create filepath
                models_dir = Path("models")
                models_dir.mkdir(exist_ok=True)

                filepath = str(models_dir / f"{model_type}_{self.ingredient_id}.pkl")

                # Serialize model
                success = model.serialize(filepath)

                if success:
                    # Register in MongoDB
                    version = await self.model_registry.register_model(
                        model_name=f"{model_type}_{self.ingredient_name}",
                        ingredient_id=self.ingredient_id,
                        ingredient_name=self.ingredient_name,
                        model_type=model_type,
                        filepath=filepath,
                        metrics=model.training_metadata.get("metrics", {}),
                        hyperparameters=model.training_metadata.get("hyperparameters", {}),
                        training_data_days=self.days_of_data,
                        features_used=model.training_metadata.get("features_used", [])
                    )

                    stored_models.append({
                        "model_type": model_type,
                        "version": version,
                        "filepath": filepath
                    })

                    logger.info(f"Stored {model_type} {version}")

            return {
                "success": True,
                "models_stored": len(stored_models),
                "details": stored_models
            }

        except Exception as e:
            logger.error(f"Model storage failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _generate_report(self, **kwargs) -> Dict[str, Any]:
        """Generate comprehensive training report"""
        training_results = kwargs.get("training_results", {})
        metrics = training_results.get("metrics", {})

        # Find best model
        best_mape = float('inf')
        best_model = None

        for model_type, model_metrics in metrics.items():
            if model_metrics["mape"] < best_mape:
                best_mape = model_metrics["mape"]
                best_model = model_type

        return {
            "success": True,
            "ingredient_id": self.ingredient_id,
            "ingredient_name": self.ingredient_name,
            "trained_at": now_ist().isoformat(),
            "data_status": kwargs.get("data_status", {}),
            "features_status": kwargs.get("features_status", {}),
            "outlier_status": kwargs.get("outlier_status", {}),
            "strategy": kwargs.get("strategy", {}),
            "training_results": training_results,
            "storage_status": kwargs.get("storage_status", {}),
            "best_model": best_model,
            "best_mape": round(best_mape, 2) if best_mape != float('inf') else None,
            "models_trained": list(metrics.keys())
        }

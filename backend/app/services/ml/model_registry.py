"""
Model Registry for ML Models

Manages storage, versioning, and retrieval of trained ML models.
Uses MongoDB for metadata and filesystem for model files.

Features:
- Model versioning
- Metadata tracking (accuracy, training date, hyperparameters)
- Automatic old model cleanup
- Model comparison
"""

import os
import json
import logging
from datetime import datetime
from app.utils.timezone import now_ist
from typing import Dict, List, Optional, Any
from pathlib import Path

from app.core.database import get_database
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Registry for trained ML models

    Storage structure:
    - MongoDB: Model metadata (accuracy, version, training date)
    - Filesystem: Serialized model files

    Example:
    /backend/models/
        prophet_chicken_breast_v1.json
        xgboost_chicken_breast_v1.pkl
        sarima_chicken_breast_v1.pkl
    """

    def __init__(self, models_dir: str = "models"):
        """
        Initialize model registry

        Args:
            models_dir: Directory for storing model files
        """
        self.settings = get_settings()
        self.db = get_database()
        self.models_collection = self.db["ml_models"]

        # Create models directory
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    async def register_model(
        self,
        model_name: str,
        ingredient_id: str,
        ingredient_name: str,
        model_type: str,
        filepath: str,
        metrics: Dict[str, float],
        hyperparameters: Optional[Dict[str, Any]] = None,
        training_data_days: int = 90,
        features_used: Optional[List[str]] = None
    ) -> str:
        """
        Register a trained model

        Args:
            model_name: Unique model name (e.g., "prophet_chicken_breast")
            ingredient_id: Ingredient ID
            ingredient_name: Ingredient name
            model_type: Model type ("prophet", "sarima", "xgboost")
            filepath: Path to serialized model file
            metrics: Training metrics (MAE, RMSE, MAPE, R²)
            hyperparameters: Model hyperparameters
            training_data_days: Number of days of training data
            features_used: List of features used in training

        Returns:
            Model version string (e.g., "v1", "v2")
        """
        # Get next version number
        existing_models = await self.models_collection.find({
            "ingredient_id": ingredient_id,
            "model_type": model_type
        }).sort("version", -1).limit(1).to_list(length=1)

        if existing_models:
            last_version = existing_models[0]["version"]
            version_num = int(last_version.replace("v", "")) + 1
        else:
            version_num = 1

        version = f"v{version_num}"

        # Store metadata in MongoDB
        model_doc = {
            "model_name": model_name,
            "ingredient_id": ingredient_id,
            "ingredient_name": ingredient_name,
            "model_type": model_type,
            "version": version,
            "filepath": filepath,
            "metrics": metrics,
            "hyperparameters": hyperparameters or {},
            "training_data_days": training_data_days,
            "features_used": features_used or [],
            "trained_at": now_ist(),
            "is_active": True,
            "is_production": False
        }

        await self.models_collection.insert_one(model_doc)

        logger.info(
            f"Registered model {model_name} {version} for {ingredient_name} "
            f"(MAPE: {metrics.get('mape', 0):.2f}%)"
        )

        return version

    async def get_model(
        self,
        ingredient_id: str,
        model_type: str,
        version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get model metadata

        Args:
            ingredient_id: Ingredient ID
            model_type: Model type
            version: Specific version (if None, returns latest)

        Returns:
            Model metadata dict or None if not found
        """
        query = {
            "ingredient_id": ingredient_id,
            "model_type": model_type,
            "is_active": True
        }

        if version:
            query["version"] = version
            model = await self.models_collection.find_one(query)
        else:
            # Get latest version
            models = await self.models_collection.find(query).sort(
                "trained_at", -1
            ).limit(1).to_list(length=1)
            model = models[0] if models else None

        return model

    async def get_best_model(
        self,
        ingredient_id: str,
        model_types: Optional[List[str]] = None,
        metric: str = "mape"
    ) -> Optional[Dict[str, Any]]:
        """
        Get best performing model for an ingredient

        Args:
            ingredient_id: Ingredient ID
            model_types: Filter by model types (if None, considers all)
            metric: Metric to optimize ("mape", "mae", "rmse")

        Returns:
            Best model metadata or None
        """
        query = {
            "ingredient_id": ingredient_id,
            "is_active": True
        }

        if model_types:
            query["model_type"] = {"$in": model_types}

        models = await self.models_collection.find(query).to_list(length=None)

        if not models:
            return None

        # Sort by metric (lower is better for MAE/RMSE/MAPE)
        best_model = min(
            models,
            key=lambda m: m["metrics"].get(metric, float('inf'))
        )

        return best_model

    async def set_production_model(
        self,
        ingredient_id: str,
        model_type: str,
        version: str
    ) -> bool:
        """
        Set a model as production model

        Args:
            ingredient_id: Ingredient ID
            model_type: Model type
            version: Model version

        Returns:
            True if successful
        """
        # Unset existing production model
        await self.models_collection.update_many(
            {
                "ingredient_id": ingredient_id,
                "model_type": model_type,
                "is_production": True
            },
            {"$set": {"is_production": False}}
        )

        # Set new production model
        result = await self.models_collection.update_one(
            {
                "ingredient_id": ingredient_id,
                "model_type": model_type,
                "version": version
            },
            {"$set": {"is_production": True}}
        )

        if result.modified_count > 0:
            logger.info(
                f"Set {model_type} {version} as production for ingredient {ingredient_id}"
            )
            return True

        return False

    async def compare_models(
        self,
        ingredient_id: str,
        metric: str = "mape"
    ) -> List[Dict[str, Any]]:
        """
        Compare all models for an ingredient

        Args:
            ingredient_id: Ingredient ID
            metric: Metric to compare

        Returns:
            List of models sorted by performance
        """
        models = await self.models_collection.find({
            "ingredient_id": ingredient_id,
            "is_active": True
        }).to_list(length=None)

        # Sort by metric (lower is better)
        sorted_models = sorted(
            models,
            key=lambda m: m["metrics"].get(metric, float('inf'))
        )

        return [
            {
                "model_type": m["model_type"],
                "version": m["version"],
                "mape": m["metrics"].get("mape"),
                "mae": m["metrics"].get("mae"),
                "rmse": m["metrics"].get("rmse"),
                "r2": m["metrics"].get("r2"),
                "trained_at": m["trained_at"],
                "is_production": m.get("is_production", False)
            }
            for m in sorted_models
        ]

    async def delete_model(
        self,
        ingredient_id: str,
        model_type: str,
        version: str
    ) -> bool:
        """
        Delete a model (soft delete)

        Args:
            ingredient_id: Ingredient ID
            model_type: Model type
            version: Model version

        Returns:
            True if successful
        """
        result = await self.models_collection.update_one(
            {
                "ingredient_id": ingredient_id,
                "model_type": model_type,
                "version": version
            },
            {"$set": {"is_active": False}}
        )

        if result.modified_count > 0:
            logger.info(f"Deleted {model_type} {version} for ingredient {ingredient_id}")
            return True

        return False

    async def cleanup_old_models(
        self,
        ingredient_id: str,
        keep_latest_n: int = 3
    ) -> int:
        """
        Clean up old model versions

        Keeps only the N most recent versions per model type.

        Args:
            ingredient_id: Ingredient ID
            keep_latest_n: Number of versions to keep

        Returns:
            Number of models deleted
        """
        deleted_count = 0

        # Get all model types for this ingredient
        model_types = await self.models_collection.distinct(
            "model_type",
            {"ingredient_id": ingredient_id, "is_active": True}
        )

        for model_type in model_types:
            # Get all versions sorted by date
            models = await self.models_collection.find({
                "ingredient_id": ingredient_id,
                "model_type": model_type,
                "is_active": True
            }).sort("trained_at", -1).to_list(length=None)

            # Delete old versions (keep latest N)
            if len(models) > keep_latest_n:
                for old_model in models[keep_latest_n:]:
                    # Don't delete production models
                    if not old_model.get("is_production", False):
                        await self.delete_model(
                            ingredient_id,
                            model_type,
                            old_model["version"]
                        )
                        deleted_count += 1

        logger.info(f"Cleaned up {deleted_count} old models for ingredient {ingredient_id}")
        return deleted_count

    async def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics

        Returns:
            Statistics about stored models
        """
        total_models = await self.models_collection.count_documents({"is_active": True})
        production_models = await self.models_collection.count_documents({
            "is_active": True,
            "is_production": True
        })

        # Count by model type
        model_type_counts = {}
        for model_type in ["prophet", "sarima", "xgboost"]:
            count = await self.models_collection.count_documents({
                "is_active": True,
                "model_type": model_type
            })
            model_type_counts[model_type] = count

        # Average MAPE
        models = await self.models_collection.find({"is_active": True}).to_list(length=None)
        avg_mape = sum(m["metrics"].get("mape", 0) for m in models) / max(len(models), 1)

        return {
            "total_models": total_models,
            "production_models": production_models,
            "model_type_counts": model_type_counts,
            "average_mape": round(avg_mape, 2),
            "models_dir": str(self.models_dir)
        }


# Singleton instance
_model_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Get singleton model registry instance"""
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry()
    return _model_registry

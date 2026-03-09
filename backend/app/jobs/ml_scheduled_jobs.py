"""
Scheduled ML Jobs

Automated jobs for ML model maintenance:
- Weekly model retraining (Sunday 2 AM)
- Daily weather data storage (5 AM)
- Model performance monitoring
- Drift detection

Register these jobs with APScheduler in the orchestrator.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.services.ml.training_pipeline import TrainingPipeline
from app.core.database import get_database

logger = logging.getLogger(__name__)


async def weekly_model_retraining() -> Dict[str, Any]:
    """
    Weekly automated model retraining

    Runs every Sunday at 2:00 AM IST
    - Retrains all models with last 90 days of data
    - Updates model registry
    - Sends performance report

    Returns:
        Retraining summary
    """
    logger.info("="*60)
    logger.info("WEEKLY MODEL RETRAINING - Starting")
    logger.info(f"Time: {datetime.utcnow().isoformat()}")
    logger.info("="*60)

    start_time = datetime.utcnow()

    try:
        db = get_database()

        # Get all ingredients that need retraining
        # TODO: Query from your actual schema
        ingredients = await _get_active_ingredients(db)

        logger.info(f"Retraining models for {len(ingredients)} ingredients")

        results = []
        successful = 0
        failed = 0

        for ingredient in ingredients:
            try:
                logger.info(f"\nRetraining: {ingredient['name']}")

                pipeline = TrainingPipeline(
                    ingredient_id=ingredient["id"],
                    ingredient_name=ingredient["name"],
                    lookback_days=90,  # Last 90 days
                    remove_outliers=True
                )

                result = await pipeline.run(
                    validate_only=False,
                    hyperparameter_tuning=False  # Skip tuning for weekly retraining (too slow)
                )

                if result["success"]:
                    successful += 1
                    logger.info(f"✓ {ingredient['name']}: MAPE {result.get('best_mape', 'N/A')}%")
                else:
                    failed += 1
                    logger.error(f"✗ {ingredient['name']}: {result.get('error', 'Unknown')}")

                results.append(result)

            except Exception as e:
                logger.error(f"✗ {ingredient['name']} failed: {e}")
                failed += 1
                results.append({
                    "success": False,
                    "ingredient_id": ingredient["id"],
                    "error": str(e)
                })

        duration = (datetime.utcnow() - start_time).total_seconds()

        summary = {
            "success": True,
            "retrained_at": start_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "total_ingredients": len(ingredients),
            "successful": successful,
            "failed": failed,
            "results": results
        }

        logger.info("\n" + "="*60)
        logger.info("WEEKLY MODEL RETRAINING - Complete")
        logger.info(f"Duration: {duration:.1f}s")
        logger.info(f"Successful: {successful}/{len(ingredients)}")
        logger.info(f"Failed: {failed}/{len(ingredients)}")
        logger.info("="*60)

        # Store retraining report
        await _store_retraining_report(db, summary)

        return summary

    except Exception as e:
        logger.error(f"Weekly retraining failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "retrained_at": start_time.isoformat()
        }


async def monitor_model_performance() -> Dict[str, Any]:
    """
    Monitor model performance and detect drift

    Runs daily at 6:00 AM IST
    - Compare recent predictions vs actuals
    - Calculate daily MAPE
    - Detect accuracy degradation
    - Trigger retraining if needed

    Returns:
        Monitoring summary
    """
    logger.info("Monitoring model performance...")

    try:
        db = get_database()

        # Get predictions from last 7 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)

        # TODO: Query predictions and actuals from database
        # For now, placeholder

        # Check for drift (MAPE degraded >10% from training)
        drift_detected = []

        # If drift detected, trigger retraining
        if drift_detected:
            logger.warning(f"Drift detected for {len(drift_detected)} ingredients")
            # TODO: Trigger retraining for affected ingredients

        return {
            "success": True,
            "monitored_at": datetime.utcnow().isoformat(),
            "period_days": 7,
            "drift_detected": len(drift_detected),
            "ingredients_with_drift": drift_detected
        }

    except Exception as e:
        logger.error(f"Performance monitoring failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def cleanup_old_models() -> Dict[str, Any]:
    """
    Clean up old model versions

    Runs monthly on the 1st at 3:00 AM IST
    - Keep latest 3 versions per model type
    - Delete older versions
    - Free up storage space

    Returns:
        Cleanup summary
    """
    logger.info("Cleaning up old model versions...")

    try:
        from app.services.ml.model_registry import get_model_registry
        model_registry = get_model_registry()

        # Get all ingredients
        ingredients = await _get_active_ingredients(get_database())

        total_deleted = 0

        for ingredient in ingredients:
            deleted = await model_registry.cleanup_old_models(
                ingredient_id=ingredient["id"],
                keep_latest_n=3
            )
            total_deleted += deleted

        logger.info(f"Cleaned up {total_deleted} old model versions")

        return {
            "success": True,
            "cleaned_at": datetime.utcnow().isoformat(),
            "models_deleted": total_deleted
        }

    except Exception as e:
        logger.error(f"Model cleanup failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def _get_active_ingredients(db) -> List[Dict[str, str]]:
    """
    Get list of active ingredients that need ML models

    TODO: Query from actual database schema

    Args:
        db: Database connection

    Returns:
        List of ingredient dicts with id and name
    """
    # Placeholder - replace with actual query
    return [
        {"id": "chicken_breast_001", "name": "Chicken Breast"},
        {"id": "tomato_001", "name": "Tomatoes"},
        {"id": "onion_001", "name": "Onions"}
    ]


async def _store_retraining_report(db, summary: Dict[str, Any]) -> None:
    """
    Store retraining report in database

    Args:
        db: Database connection
        summary: Retraining summary
    """
    try:
        collection = db["ml_retraining_reports"]
        await collection.insert_one(summary)
        logger.info("Stored retraining report")

    except Exception as e:
        logger.error(f"Failed to store retraining report: {e}")


# Job schedule configuration
SCHEDULED_JOBS = [
    {
        "id": "weekly_model_retraining",
        "name": "Weekly Model Retraining",
        "function": weekly_model_retraining,
        "trigger": "cron",
        "day_of_week": "sun",  # Sunday
        "hour": 2,  # 2 AM IST
        "minute": 0,
        "timezone": "Asia/Kolkata"
    },
    {
        "id": "daily_performance_monitoring",
        "name": "Daily Model Performance Monitoring",
        "function": monitor_model_performance,
        "trigger": "cron",
        "hour": 6,  # 6 AM IST
        "minute": 0,
        "timezone": "Asia/Kolkata"
    },
    {
        "id": "monthly_model_cleanup",
        "name": "Monthly Old Model Cleanup",
        "function": cleanup_old_models,
        "trigger": "cron",
        "day": 1,  # 1st of month
        "hour": 3,  # 3 AM IST
        "minute": 0,
        "timezone": "Asia/Kolkata"
    }
]

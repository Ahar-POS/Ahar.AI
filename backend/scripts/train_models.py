"""
Manual Model Training Script

Run this script to train ML models for demand forecasting.

Usage:
    # Train for specific ingredient:
    python scripts/train_models.py --ingredient-id "chicken_breast_001"

    # Train for all ingredients:
    python scripts/train_models.py --all

    # Train with hyperparameter tuning:
    python scripts/train_models.py --ingredient-id "chicken_breast_001" --tune

    # Validate data only (no training):
    python scripts/train_models.py --ingredient-id "chicken_breast_001" --validate-only
"""

import asyncio
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import get_database
from app.services.ml.training_pipeline import TrainingPipeline
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def train_ingredient(
    ingredient_id: str,
    ingredient_name: str,
    lookback_days: int = 90,
    remove_outliers: bool = True,
    validate_only: bool = False,
    hyperparameter_tuning: bool = False
) -> Dict[str, Any]:
    """
    Train models for a single ingredient

    Args:
        ingredient_id: Ingredient ID
        ingredient_name: Ingredient name
        lookback_days: Days of historical data
        remove_outliers: Whether to remove outliers
        validate_only: Only validate data
        hyperparameter_tuning: Run hyperparameter optimization

    Returns:
        Training results
    """
    logger.info(f"{'='*60}")
    logger.info(f"Training: {ingredient_name} ({ingredient_id})")
    logger.info(f"{'='*60}")

    pipeline = TrainingPipeline(
        ingredient_id=ingredient_id,
        ingredient_name=ingredient_name,
        lookback_days=lookback_days,
        remove_outliers=remove_outliers
    )

    result = await pipeline.run(
        validate_only=validate_only,
        hyperparameter_tuning=hyperparameter_tuning
    )

    # Print summary
    if result["success"]:
        logger.info("\n" + "="*60)
        logger.info("TRAINING SUMMARY")
        logger.info("="*60)
        logger.info(f"Ingredient: {ingredient_name}")
        logger.info(f"Data Tier: {result.get('data_status', {}).get('data_tier', 'Unknown')}")
        logger.info(f"Days of Data: {result.get('data_status', {}).get('days_of_data', 0)}")
        logger.info(f"Models Trained: {', '.join(result.get('models_trained', []))}")
        logger.info(f"Best Model: {result.get('best_model', 'Unknown')}")
        logger.info(f"Best MAPE: {result.get('best_mape', 'N/A')}%")
        logger.info(f"Duration: {result.get('pipeline_duration_seconds', 0):.1f}s")
        logger.info("="*60 + "\n")
    else:
        logger.error(f"\n✗ Training failed: {result.get('error', 'Unknown error')}\n")

    return result


async def train_all_ingredients(
    lookback_days: int = 90,
    remove_outliers: bool = True,
    hyperparameter_tuning: bool = False
) -> List[Dict[str, Any]]:
    """
    Train models for all ingredients

    Args:
        lookback_days: Days of historical data
        remove_outliers: Whether to remove outliers
        hyperparameter_tuning: Run hyperparameter optimization

    Returns:
        List of training results
    """
    db = get_database()

    # Get all ingredients from database
    # TODO: Query actual ingredients from your schema
    # For now, using placeholder
    ingredients = [
        {"id": "chicken_breast_001", "name": "Chicken Breast"},
        {"id": "tomato_001", "name": "Tomatoes"},
        {"id": "onion_001", "name": "Onions"}
    ]

    logger.info(f"Training models for {len(ingredients)} ingredients...")

    results = []

    for ingredient in ingredients:
        try:
            result = await train_ingredient(
                ingredient_id=ingredient["id"],
                ingredient_name=ingredient["name"],
                lookback_days=lookback_days,
                remove_outliers=remove_outliers,
                hyperparameter_tuning=hyperparameter_tuning
            )
            results.append(result)

        except Exception as e:
            logger.error(f"Failed to train {ingredient['name']}: {e}")
            results.append({
                "success": False,
                "ingredient_id": ingredient["id"],
                "error": str(e)
            })

    # Summary report
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    logger.info("\n" + "="*60)
    logger.info("OVERALL TRAINING SUMMARY")
    logger.info("="*60)
    logger.info(f"Total Ingredients: {len(results)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info("="*60 + "\n")

    return results


async def validate_setup() -> bool:
    """
    Validate that system is set up correctly

    Returns:
        True if setup is valid
    """
    logger.info("Validating system setup...")

    issues = []

    # Check database connection
    try:
        db = get_database()
        await db.command("ping")
        logger.info("✓ Database connection OK")
    except Exception as e:
        issues.append(f"Database connection failed: {e}")

    # Check API keys
    settings = get_settings()

    if not settings.VISUALCROSSING_API_KEY and not settings.OPENWEATHERMAP_API_KEY:
        issues.append("No weather API key configured (VISUALCROSSING_API_KEY or OPENWEATHERMAP_API_KEY)")
    else:
        logger.info("✓ Weather API key configured")

    # Check models directory
    models_dir = Path("models")
    if not models_dir.exists():
        models_dir.mkdir(parents=True)
        logger.info("✓ Created models directory")
    else:
        logger.info("✓ Models directory exists")

    if issues:
        logger.error("\n✗ Setup validation failed:")
        for issue in issues:
            logger.error(f"  - {issue}")
        return False

    logger.info("✓ System setup validated\n")
    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Train ML models for demand forecasting"
    )

    parser.add_argument(
        "--ingredient-id",
        type=str,
        help="Ingredient ID to train for"
    )

    parser.add_argument(
        "--ingredient-name",
        type=str,
        help="Ingredient name (required if --ingredient-id used)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Train models for all ingredients"
    )

    parser.add_argument(
        "--lookback-days",
        type=int,
        default=90,
        help="Days of historical data to use (default: 90)"
    )

    parser.add_argument(
        "--no-outlier-removal",
        action="store_true",
        help="Don't remove outliers from training data"
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate data, don't train models"
    )

    parser.add_argument(
        "--tune",
        action="store_true",
        help="Run hyperparameter tuning (slower but better accuracy)"
    )

    parser.add_argument(
        "--validate-setup",
        action="store_true",
        help="Validate system setup and exit"
    )

    args = parser.parse_args()

    # Validate setup
    if args.validate_setup:
        is_valid = asyncio.run(validate_setup())
        sys.exit(0 if is_valid else 1)

    # Validate arguments
    if not args.all and not args.ingredient_id:
        parser.error("Either --ingredient-id or --all must be specified")

    if args.ingredient_id and not args.ingredient_name:
        parser.error("--ingredient-name is required when using --ingredient-id")

    # Run training
    try:
        if args.all:
            results = asyncio.run(train_all_ingredients(
                lookback_days=args.lookback_days,
                remove_outliers=not args.no_outlier_removal,
                hyperparameter_tuning=args.tune
            ))

            # Exit code based on success rate
            successful = sum(1 for r in results if r["success"])
            sys.exit(0 if successful == len(results) else 1)

        else:
            result = asyncio.run(train_ingredient(
                ingredient_id=args.ingredient_id,
                ingredient_name=args.ingredient_name,
                lookback_days=args.lookback_days,
                remove_outliers=not args.no_outlier_removal,
                validate_only=args.validate_only,
                hyperparameter_tuning=args.tune
            ))

            sys.exit(0 if result["success"] else 1)

    except KeyboardInterrupt:
        logger.info("\nTraining interrupted by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

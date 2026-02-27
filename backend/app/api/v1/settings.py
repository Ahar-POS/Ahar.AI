"""
Restaurant Settings API routes.

Provides endpoints for managing restaurant configuration including:
- Platform commission rates
- Role salaries
- OPEX budgets
- Depreciation rates
- Tax settings
"""

from fastapi import APIRouter, HTTPException, Depends

from app.models.restaurant_settings import (
    RestaurantSettingsCreate,
    RestaurantSettingsUpdate,
    RestaurantSettingsResponse
)
from app.services.settings_service import settings_service
from app.utils.response import success_response, error_response
from app.core.dependencies import get_current_user
from app.models.user import UserResponse, UserRole

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/restaurant", response_model=dict)
async def get_restaurant_settings(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get current restaurant settings.

    Returns all configuration values for P&L calculation including
    platform rates, salaries, OPEX budgets, etc.
    """
    try:
        # Get settings for the user's restaurant
        restaurant_id = "default"  # TODO: Get from current_user when multi-tenancy is implemented

        settings = await settings_service.get_settings(restaurant_id)

        if not settings:
            # Return default settings if none exist
            return success_response(
                data=None,
                message="No settings found. Default values will be used."
            )

        return success_response(
            data=settings.model_dump(by_alias=True),
            message="Settings retrieved successfully"
        )
    except Exception as e:
        return error_response(
            code="RETRIEVAL_FAILED",
            message=f"Failed to retrieve settings: {str(e)}"
        )


@router.put("/restaurant", response_model=dict)
async def update_restaurant_settings(
    settings_update: RestaurantSettingsUpdate,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Update restaurant settings (Admin only).

    Allows updating any or all configuration values.
    Only admin users can modify settings.
    """
    # Check admin permission
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can update restaurant settings"
        )

    try:
        # Get restaurant ID
        restaurant_id = "default"  # TODO: Get from current_user when multi-tenancy is implemented

        # Update settings
        updated_settings = await settings_service.update_settings(
            restaurant_id,
            settings_update
        )

        return success_response(
            data=updated_settings.model_dump(by_alias=True),
            message="Settings updated successfully"
        )
    except ValueError as e:
        return error_response(
            code="VALIDATION_ERROR",
            message=str(e)
        )
    except Exception as e:
        return error_response(
            code="UPDATE_FAILED",
            message=f"Failed to update settings: {str(e)}"
        )


@router.post("/restaurant/initialize", response_model=dict)
async def initialize_restaurant_settings(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Initialize default restaurant settings (Admin only).

    Creates settings with default values if they don't exist.
    Useful for first-time setup.
    """
    # Check admin permission
    if current_user.role != UserRole.ADMIN:
        return error_response(
            code="FORBIDDEN",
            message="Only administrators can initialize settings"
        )

    try:
        restaurant_id = "default"  # TODO: Get from current_user when multi-tenancy is implemented

        # Create default settings
        settings = await settings_service.get_or_create_default(restaurant_id)

        return success_response(
            data=settings.model_dump(by_alias=True),
            message="Settings initialized successfully"
        )
    except Exception as e:
        return error_response(
            code="INITIALIZATION_FAILED",
            message=f"Failed to initialize settings: {str(e)}"
        )

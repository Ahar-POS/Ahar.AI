"""
Restaurant Settings Service.

Business logic for managing restaurant configuration settings.
"""

from typing import Optional
from app.models.restaurant_settings import (
    RestaurantSettingsCreate,
    RestaurantSettingsUpdate,
    RestaurantSettingsResponse,
    RestaurantSettingsInDB
)
from app.repositories.restaurant_settings_repository import RestaurantSettingsRepository


class SettingsService:
    """Service for restaurant settings operations."""

    def __init__(self):
        self.repository = RestaurantSettingsRepository()

    async def get_settings(self, restaurant_id: str) -> Optional[RestaurantSettingsResponse]:
        """
        Get restaurant settings by restaurant ID.

        Args:
            restaurant_id: Restaurant identifier

        Returns:
            Settings or None if not found
        """
        settings_doc = await self.repository.get_by_restaurant_id(restaurant_id)

        if not settings_doc:
            return None

        # Convert ObjectId to string
        if '_id' in settings_doc:
            settings_doc['_id'] = str(settings_doc['_id'])

        return RestaurantSettingsResponse(**settings_doc)

    async def get_or_create_default(self, restaurant_id: str) -> RestaurantSettingsResponse:
        """
        Get existing settings or create default if not exists.

        Args:
            restaurant_id: Restaurant identifier

        Returns:
            Settings (existing or newly created defaults)
        """
        settings_doc = await self.repository.get_or_create_default(restaurant_id)

        # Convert ObjectId to string
        if '_id' in settings_doc:
            settings_doc['_id'] = str(settings_doc['_id'])

        return RestaurantSettingsResponse(**settings_doc)

    async def update_settings(
        self,
        restaurant_id: str,
        settings_update: RestaurantSettingsUpdate
    ) -> RestaurantSettingsResponse:
        """
        Update restaurant settings.

        Args:
            restaurant_id: Restaurant identifier
            settings_update: Updated settings data

        Returns:
            Updated settings

        Raises:
            ValueError: If restaurant not found or validation fails
        """
        # Get existing settings
        existing = await self.repository.get_by_restaurant_id(restaurant_id)

        if not existing:
            raise ValueError(f"No settings found for restaurant '{restaurant_id}'. Initialize settings first.")

        # Prepare update data (only include non-None fields)
        update_data = settings_update.model_dump(exclude_none=True)

        if not update_data:
            raise ValueError("No fields to update")

        # Update settings
        updated_doc = await self.repository.update(restaurant_id, update_data)

        if not updated_doc:
            raise ValueError(f"Failed to update settings for restaurant '{restaurant_id}'")

        # Convert ObjectId to string
        if '_id' in updated_doc:
            updated_doc['_id'] = str(updated_doc['_id'])

        return RestaurantSettingsResponse(**updated_doc)

    async def create_settings(
        self,
        settings_create: RestaurantSettingsCreate
    ) -> RestaurantSettingsResponse:
        """
        Create new restaurant settings.

        Args:
            settings_create: Settings data

        Returns:
            Created settings

        Raises:
            ValueError: If settings already exist for this restaurant
        """
        # Check if settings already exist
        existing = await self.repository.get_by_restaurant_id(settings_create.restaurant_id)

        if existing:
            raise ValueError(
                f"Settings already exist for restaurant '{settings_create.restaurant_id}'. "
                "Use update endpoint instead."
            )

        # Create settings
        settings_doc = await self.repository.create(settings_create.model_dump())

        # Convert ObjectId to string
        if '_id' in settings_doc:
            settings_doc['_id'] = str(settings_doc['_id'])

        return RestaurantSettingsResponse(**settings_doc)


# Global service instance
settings_service = SettingsService()

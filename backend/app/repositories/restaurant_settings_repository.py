"""Repository for restaurant settings operations."""

from datetime import datetime
from app.utils.timezone import now_ist
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database


class RestaurantSettingsRepository:
    """Repository for restaurant settings CRUD operations."""

    def __init__(self):
        self.collection: AsyncIOMotorCollection = None

    def _get_collection(self) -> AsyncIOMotorCollection:
        """Get restaurant_settings collection."""
        if self.collection is None:
            db = get_database()
            self.collection = db.restaurant_settings
        return self.collection

    async def create(self, settings_data: dict) -> dict:
        """Create new restaurant settings."""
        collection = self._get_collection()
        settings_data["created_at"] = now_ist()
        settings_data["updated_at"] = now_ist()

        result = await collection.insert_one(settings_data)
        created_settings = await collection.find_one({"_id": result.inserted_id})
        return created_settings

    async def get_by_restaurant_id(self, restaurant_id: str) -> Optional[dict]:
        """Get settings by restaurant ID."""
        collection = self._get_collection()
        return await collection.find_one({"restaurant_id": restaurant_id})

    async def get_by_id(self, settings_id: str) -> Optional[dict]:
        """Get settings by ID."""
        collection = self._get_collection()
        return await collection.find_one({"_id": ObjectId(settings_id)})

    async def update(self, restaurant_id: str, update_data: dict) -> Optional[dict]:
        """Update restaurant settings."""
        collection = self._get_collection()
        update_data["updated_at"] = now_ist()

        result = await collection.find_one_and_update(
            {"restaurant_id": restaurant_id},
            {"$set": update_data},
            return_document=True
        )
        return result

    async def delete(self, restaurant_id: str) -> bool:
        """Delete restaurant settings."""
        collection = self._get_collection()
        result = await collection.delete_one({"restaurant_id": restaurant_id})
        return result.deleted_count > 0

    async def get_or_create_default(self, restaurant_id: str) -> dict:
        """Get settings or create default if not exists."""
        settings = await self.get_by_restaurant_id(restaurant_id)
        if settings:
            return settings

        # Create default settings
        from app.models.restaurant_settings import RestaurantSettingsCreate
        default_settings = RestaurantSettingsCreate(restaurant_id=restaurant_id)
        return await self.create(default_settings.model_dump())

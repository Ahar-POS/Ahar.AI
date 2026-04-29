"""Repository for fixed asset operations."""

from datetime import datetime
from app.utils.timezone import now_ist
from typing import List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database


class FixedAssetRepository:
    """Repository for fixed asset CRUD operations."""

    def __init__(self):
        self.collection: AsyncIOMotorCollection = None

    def _get_collection(self) -> AsyncIOMotorCollection:
        """Get fixed_assets collection."""
        if self.collection is None:
            db = get_database()
            self.collection = db.fixed_assets
        return self.collection

    async def create(self, asset_data: dict) -> dict:
        """Create a new fixed asset."""
        collection = self._get_collection()
        asset_data["created_at"] = now_ist()
        asset_data["updated_at"] = now_ist()

        result = await collection.insert_one(asset_data)
        created_asset = await collection.find_one({"_id": result.inserted_id})
        return created_asset

    async def get_by_id(self, asset_id: str) -> Optional[dict]:
        """Get fixed asset by ID."""
        collection = self._get_collection()
        return await collection.find_one({"_id": ObjectId(asset_id)})

    async def get_by_asset_id(self, asset_id: str) -> Optional[dict]:
        """Get fixed asset by asset_id."""
        collection = self._get_collection()
        return await collection.find_one({"asset_id": asset_id})

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None
    ) -> List[dict]:
        """Get all fixed assets with optional filters."""
        collection = self._get_collection()

        query = {}
        if category:
            query["category"] = category

        cursor = collection.find(query).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def update(self, asset_id: str, update_data: dict) -> Optional[dict]:
        """Update fixed asset."""
        collection = self._get_collection()
        update_data["updated_at"] = now_ist()

        result = await collection.find_one_and_update(
            {"asset_id": asset_id},
            {"$set": update_data},
            return_document=True
        )
        return result

    async def delete(self, asset_id: str) -> bool:
        """Delete fixed asset."""
        collection = self._get_collection()
        result = await collection.delete_one({"asset_id": asset_id})
        return result.deleted_count > 0

    async def count(self, category: Optional[str] = None) -> int:
        """Count fixed assets."""
        collection = self._get_collection()
        query = {}
        if category:
            query["category"] = category
        return await collection.count_documents(query)

    async def get_total_monthly_depreciation(self) -> int:
        """Calculate total monthly depreciation across all assets."""
        collection = self._get_collection()
        assets = await collection.find({}).to_list(length=None)

        total_depreciation = 0
        for asset in assets:
            purchase_cost = asset.get("purchase_cost_inr", 0)
            useful_life = asset.get("useful_life_months", 1)
            monthly_depreciation = purchase_cost // useful_life
            total_depreciation += monthly_depreciation

        return total_depreciation

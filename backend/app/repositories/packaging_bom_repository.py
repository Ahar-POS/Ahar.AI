"""Repository for packaging BOM operations."""

from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database


class PackagingBOMRepository:
    """Repository for packaging BOM CRUD operations."""

    def __init__(self):
        self.collection: AsyncIOMotorCollection = None

    def _get_collection(self) -> AsyncIOMotorCollection:
        """Get packaging_bom collection."""
        if self.collection is None:
            db = get_database()
            self.collection = db.packaging_bom
        return self.collection

    async def create(self, bom_data: dict) -> dict:
        """Create a new packaging BOM entry."""
        collection = self._get_collection()
        bom_data["created_at"] = datetime.utcnow()
        bom_data["updated_at"] = datetime.utcnow()

        result = await collection.insert_one(bom_data)
        created_bom = await collection.find_one({"_id": result.inserted_id})
        return created_bom

    async def get_by_id(self, bom_id: str) -> Optional[dict]:
        """Get packaging BOM by ID."""
        collection = self._get_collection()
        return await collection.find_one({"_id": ObjectId(bom_id)})

    async def get_by_menu_item(self, menu_item_id: str) -> List[dict]:
        """Get all packaging requirements for a menu item."""
        collection = self._get_collection()
        cursor = collection.find({"menu_item_id": menu_item_id})
        return await cursor.to_list(length=None)

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[dict]:
        """Get all packaging BOM entries."""
        collection = self._get_collection()
        cursor = collection.find({}).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def update(self, bom_id: str, update_data: dict) -> Optional[dict]:
        """Update packaging BOM entry."""
        collection = self._get_collection()
        update_data["updated_at"] = datetime.utcnow()

        result = await collection.find_one_and_update(
            {"_id": ObjectId(bom_id)},
            {"$set": update_data},
            return_document=True
        )
        return result

    async def delete(self, bom_id: str) -> bool:
        """Delete packaging BOM entry."""
        collection = self._get_collection()
        result = await collection.delete_one({"_id": ObjectId(bom_id)})
        return result.deleted_count > 0

    async def delete_by_menu_item(self, menu_item_id: str) -> int:
        """Delete all packaging BOM entries for a menu item."""
        collection = self._get_collection()
        result = await collection.delete_many({"menu_item_id": menu_item_id})
        return result.deleted_count

    async def count(self) -> int:
        """Count packaging BOM entries."""
        collection = self._get_collection()
        return await collection.count_documents({})

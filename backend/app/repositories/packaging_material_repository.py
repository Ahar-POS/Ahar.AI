"""Repository for packaging material operations."""

from datetime import datetime
from app.utils.timezone import now_ist
from typing import List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database


class PackagingMaterialRepository:
    """Repository for packaging material CRUD operations."""

    def __init__(self):
        self.collection: AsyncIOMotorCollection = None

    def _get_collection(self) -> AsyncIOMotorCollection:
        """Get packaging_materials collection."""
        if self.collection is None:
            db = get_database()
            self.collection = db.packaging_materials
        return self.collection

    async def create(self, material_data: dict) -> dict:
        """Create a new packaging material."""
        collection = self._get_collection()
        material_data["created_at"] = now_ist()
        material_data["updated_at"] = now_ist()

        result = await collection.insert_one(material_data)
        created_material = await collection.find_one({"_id": result.inserted_id})
        return created_material

    async def get_by_id(self, material_id: str) -> Optional[dict]:
        """Get packaging material by ID."""
        collection = self._get_collection()
        return await collection.find_one({"_id": ObjectId(material_id)})

    async def get_by_packaging_id(self, packaging_id: str) -> Optional[dict]:
        """Get packaging material by packaging_id."""
        collection = self._get_collection()
        return await collection.find_one({"packaging_id": packaging_id})

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None
    ) -> List[dict]:
        """Get all packaging materials with optional filters."""
        collection = self._get_collection()

        query = {}
        if category:
            query["category"] = category

        cursor = collection.find(query).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def update(self, packaging_id: str, update_data: dict) -> Optional[dict]:
        """Update packaging material."""
        collection = self._get_collection()
        update_data["updated_at"] = now_ist()

        result = await collection.find_one_and_update(
            {"packaging_id": packaging_id},
            {"$set": update_data},
            return_document=True
        )
        return result

    async def delete(self, packaging_id: str) -> bool:
        """Delete packaging material."""
        collection = self._get_collection()
        result = await collection.delete_one({"packaging_id": packaging_id})
        return result.deleted_count > 0

    async def count(self, category: Optional[str] = None) -> int:
        """Count packaging materials."""
        collection = self._get_collection()
        query = {}
        if category:
            query["category"] = category
        return await collection.count_documents(query)

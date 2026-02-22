from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database


class InventoryRepository:
    """Repository for raw material inventory operations"""

    def __init__(self):
        self.collection: AsyncIOMotorCollection = None

    def _get_collection(self) -> AsyncIOMotorCollection:
        """Get inventory collection"""
        if self.collection is None:
            db = get_database()
            self.collection = db.raw_material_inventory
        return self.collection

    async def create(self, item_data: dict) -> dict:
        """Create a new inventory item"""
        collection = self._get_collection()
        item_data["created_at"] = datetime.utcnow()
        item_data["updated_at"] = datetime.utcnow()

        result = await collection.insert_one(item_data)
        created_item = await collection.find_one({"_id": result.inserted_id})
        return created_item

    async def get_by_id(self, item_id: str) -> Optional[dict]:
        """Get inventory item by ID"""
        collection = self._get_collection()
        return await collection.find_one({"_id": ObjectId(item_id)})

    async def get_by_material_id(self, material_id: str) -> Optional[dict]:
        """Get inventory item by material ID"""
        collection = self._get_collection()
        return await collection.find_one({"material_id": material_id})

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        is_perishable: Optional[str] = None
    ) -> List[dict]:
        """Get all inventory items with optional filters"""
        collection = self._get_collection()

        query = {}
        if category:
            query["category"] = category
        if is_perishable:
            query["is_perishable"] = is_perishable

        cursor = collection.find(query).skip(skip).limit(limit).sort("material_id", 1)
        return await cursor.to_list(length=limit)

    async def count(
        self,
        category: Optional[str] = None,
        is_perishable: Optional[str] = None
    ) -> int:
        """Count inventory items with optional filters"""
        collection = self._get_collection()

        query = {}
        if category:
            query["category"] = category
        if is_perishable:
            query["is_perishable"] = is_perishable

        return await collection.count_documents(query)

    async def update(self, item_id: str, update_data: dict) -> Optional[dict]:
        """Update an inventory item"""
        collection = self._get_collection()
        update_data["updated_at"] = datetime.utcnow()

        result = await collection.find_one_and_update(
            {"_id": ObjectId(item_id)},
            {"$set": update_data},
            return_document=True
        )
        return result

    async def delete(self, item_id: str) -> bool:
        """Delete an inventory item"""
        collection = self._get_collection()
        result = await collection.delete_one({"_id": ObjectId(item_id)})
        return result.deleted_count > 0

    async def get_low_stock_items(self) -> List[dict]:
        """Get items where current stock is below reorder level"""
        collection = self._get_collection()
        cursor = collection.find({
            "$expr": {"$lte": ["$current_stock", "$reorder_level"]}
        }).sort("material_id", 1)
        return await cursor.to_list(length=None)

    async def search_by_name(self, query: str) -> List[dict]:
        """Search inventory items by name substring (case-insensitive)"""
        collection = self._get_collection()
        cursor = collection.find(
            {"material_name": {"$regex": query, "$options": "i"}}
        ).sort("material_id", 1)
        return await cursor.to_list(length=None)

    async def bulk_create(self, items: List[dict]) -> int:
        """Bulk create inventory items"""
        collection = self._get_collection()
        now = datetime.utcnow()

        for item in items:
            item["created_at"] = now
            item["updated_at"] = now

        result = await collection.insert_many(items)
        return len(result.inserted_ids)


inventory_repository = InventoryRepository()

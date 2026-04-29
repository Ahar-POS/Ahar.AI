"""
Repository for purchase order operations.
"""
from datetime import datetime
from app.utils.timezone import now_ist
from typing import List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database
from app.models.document import POStatus


class PurchaseOrderRepository:
    """Repository for purchase order operations."""

    def __init__(self):
        self.collection: AsyncIOMotorCollection = None

    def _get_collection(self) -> AsyncIOMotorCollection:
        """Get purchase_orders collection."""
        if self.collection is None:
            db = get_database()
            self.collection = db.purchase_orders
        return self.collection

    async def create(self, po_data: dict) -> dict:
        """Create a new purchase order."""
        collection = self._get_collection()
        po_data["created_at"] = now_ist()
        po_data["updated_at"] = now_ist()

        result = await collection.insert_one(po_data)
        created_po = await collection.find_one({"_id": result.inserted_id})
        return created_po

    async def get_by_id(self, po_id: str) -> Optional[dict]:
        """Get purchase order by ID."""
        collection = self._get_collection()
        return await collection.find_one({"_id": ObjectId(po_id)})

    async def get_by_po_number(self, po_number: str) -> Optional[dict]:
        """Get purchase order by PO number."""
        collection = self._get_collection()
        return await collection.find_one({"po_number": po_number})

    async def get_by_ocr_result_id(self, ocr_result_id: str) -> Optional[dict]:
        """Get purchase order by OCR result ID."""
        collection = self._get_collection()
        return await collection.find_one({"ocr_result_id": ocr_result_id})

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
        supplier_id: Optional[str] = None,
        status: Optional[POStatus] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[dict]:
        """Get all purchase orders with optional filters."""
        collection = self._get_collection()

        query = {}
        if supplier_id:
            query["supplier_id"] = supplier_id
        if status:
            query["status"] = status.value

        # Date range filter on PO date
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["po_date"] = date_query

        cursor = collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        return await cursor.to_list(length=limit)

    async def count(
        self,
        supplier_id: Optional[str] = None,
        status: Optional[POStatus] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> int:
        """Count purchase orders with optional filters."""
        collection = self._get_collection()

        query = {}
        if supplier_id:
            query["supplier_id"] = supplier_id
        if status:
            query["status"] = status.value

        # Date range filter on PO date
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["po_date"] = date_query

        return await collection.count_documents(query)

    async def update(self, po_id: str, update_data: dict) -> Optional[dict]:
        """Update a purchase order."""
        collection = self._get_collection()
        update_data["updated_at"] = now_ist()

        result = await collection.find_one_and_update(
            {"_id": ObjectId(po_id)},
            {"$set": update_data},
            return_document=True
        )
        return result

    async def delete(self, po_id: str) -> bool:
        """Delete a purchase order."""
        collection = self._get_collection()
        result = await collection.delete_one({"_id": ObjectId(po_id)})
        return result.deleted_count > 0

    async def find_by_supplier_and_status(
        self,
        supplier_id: str,
        statuses: List[POStatus]
    ) -> List[dict]:
        """Find purchase orders by supplier and status list."""
        collection = self._get_collection()
        status_values = [status.value for status in statuses]

        cursor = collection.find({
            "supplier_id": supplier_id,
            "status": {"$in": status_values}
        }).sort("created_at", -1)

        return await cursor.to_list(length=None)

    async def get_open_pos(self, limit: int = 100) -> List[dict]:
        """Get open purchase orders (pending or partially received)."""
        collection = self._get_collection()
        cursor = collection.find({
            "status": {
                "$in": [POStatus.PENDING.value, POStatus.PARTIALLY_RECEIVED.value]
            }
        }).sort("created_at", -1).limit(limit)

        return await cursor.to_list(length=limit)


# Singleton instance
purchase_order_repository = PurchaseOrderRepository()


def get_purchase_order_repository() -> PurchaseOrderRepository:
    """Get singleton purchase order repository instance."""
    return purchase_order_repository

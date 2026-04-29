"""
Repository for bill operations.
"""
from datetime import datetime
from app.utils.timezone import now_ist
from typing import List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database
from app.models.document import BillStatus


class BillRepository:
    """Repository for bill operations."""

    def __init__(self):
        self.collection: AsyncIOMotorCollection = None

    def _get_collection(self) -> AsyncIOMotorCollection:
        """Get bills collection."""
        if self.collection is None:
            db = get_database()
            self.collection = db.bills
        return self.collection

    async def create(self, bill_data: dict) -> dict:
        """Create a new bill."""
        collection = self._get_collection()
        bill_data["created_at"] = now_ist()
        bill_data["updated_at"] = now_ist()

        result = await collection.insert_one(bill_data)
        created_bill = await collection.find_one({"_id": result.inserted_id})
        # Backward-compatible default for records created before explicit status field
        if created_bill and "status" not in created_bill:
            created_bill["status"] = BillStatus.PENDING_REVIEW.value
        return created_bill

    async def get_by_id(self, bill_id: str) -> Optional[dict]:
        """Get bill by ID."""
        collection = self._get_collection()
        return await collection.find_one({"_id": ObjectId(bill_id)})

    async def get_by_invoice_number(self, invoice_number: str) -> Optional[dict]:
        """Get bill by invoice number."""
        collection = self._get_collection()
        return await collection.find_one({"invoice_number": invoice_number})

    async def get_by_ocr_result_id(self, ocr_result_id: str) -> Optional[dict]:
        """Get bill by OCR result ID."""
        collection = self._get_collection()
        return await collection.find_one({"ocr_result_id": ocr_result_id})

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
        supplier_id: Optional[str] = None,
        status: Optional[BillStatus] = None,
        has_price_discrepancies: Optional[bool] = None,
        linked_po_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[dict]:
        """Get all bills with optional filters."""
        collection = self._get_collection()

        query = {}
        if supplier_id:
            query["supplier_id"] = supplier_id
        if status:
            query["status"] = status.value
        if has_price_discrepancies is not None:
            query["has_price_discrepancies"] = has_price_discrepancies
        if linked_po_id:
            query["linked_po_id"] = linked_po_id

        # Date range filter on invoice date
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["invoice_date"] = date_query

        cursor = collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        bills = await cursor.to_list(length=limit)
        for bill in bills:
            if "status" not in bill:
                bill["status"] = BillStatus.PENDING_REVIEW.value
        return bills

    async def count(
        self,
        supplier_id: Optional[str] = None,
        status: Optional[BillStatus] = None,
        has_price_discrepancies: Optional[bool] = None,
        linked_po_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> int:
        """Count bills with optional filters."""
        collection = self._get_collection()

        query = {}
        if supplier_id:
            query["supplier_id"] = supplier_id
        if status:
            query["status"] = status.value
        if has_price_discrepancies is not None:
            query["has_price_discrepancies"] = has_price_discrepancies
        if linked_po_id:
            query["linked_po_id"] = linked_po_id

        # Date range filter on invoice date
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["invoice_date"] = date_query

        return await collection.count_documents(query)

    async def update(self, bill_id: str, update_data: dict) -> Optional[dict]:
        """Update a bill."""
        collection = self._get_collection()
        update_data["updated_at"] = now_ist()

        result = await collection.find_one_and_update(
            {"_id": ObjectId(bill_id)},
            {"$set": update_data},
            return_document=True
        )
        if result and "status" not in result:
            result["status"] = BillStatus.PENDING_REVIEW.value
        return result

    async def delete(self, bill_id: str) -> bool:
        """Delete a bill."""
        collection = self._get_collection()
        result = await collection.delete_one({"_id": ObjectId(bill_id)})
        return result.deleted_count > 0

    async def get_bills_with_discrepancies(self, limit: int = 50) -> List[dict]:
        """Get bills with price discrepancies."""
        collection = self._get_collection()
        cursor = collection.find(
            {"has_price_discrepancies": True}
        ).sort("created_at", -1).limit(limit)

        return await cursor.to_list(length=limit)

    async def get_bills_by_po(self, po_id: str) -> List[dict]:
        """Get all bills linked to a specific purchase order."""
        collection = self._get_collection()
        cursor = collection.find(
            {"linked_po_id": po_id}
        ).sort("created_at", -1)

        return await cursor.to_list(length=None)


# Singleton instance
bill_repository = BillRepository()


def get_bill_repository() -> BillRepository:
    """Get singleton bill repository instance."""
    return bill_repository

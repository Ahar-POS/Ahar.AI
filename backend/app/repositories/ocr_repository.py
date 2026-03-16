"""
Repository for OCR result operations.
"""
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database
from app.models.document import DocumentStatus, DocumentType


class OCRRepository:
    """Repository for OCR result operations."""

    def __init__(self):
        self.collection: AsyncIOMotorCollection = None

    def _get_collection(self) -> AsyncIOMotorCollection:
        """Get ocr_results collection."""
        if self.collection is None:
            db = get_database()
            self.collection = db.ocr_results
        return self.collection

    async def create(self, ocr_data: dict) -> dict:
        """Create a new OCR result record."""
        collection = self._get_collection()
        ocr_data["created_at"] = datetime.utcnow()
        ocr_data["updated_at"] = datetime.utcnow()

        result = await collection.insert_one(ocr_data)
        created_ocr = await collection.find_one({"_id": result.inserted_id})
        return created_ocr

    async def get_by_id(self, ocr_id: str) -> Optional[dict]:
        """Get OCR result by ID."""
        collection = self._get_collection()
        return await collection.find_one({"_id": ObjectId(ocr_id)})

    async def get_by_document_upload_id(self, document_upload_id: str) -> Optional[dict]:
        """Get OCR result by document upload ID."""
        collection = self._get_collection()
        return await collection.find_one({"document_upload_id": document_upload_id})

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
        document_type: Optional[DocumentType] = None,
        status: Optional[DocumentStatus] = None
    ) -> List[dict]:
        """Get all OCR results with optional filters."""
        collection = self._get_collection()

        query = {}
        if document_type:
            query["document_type"] = document_type.value
        if status:
            query["status"] = status.value

        cursor = collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        return await cursor.to_list(length=limit)

    async def count(
        self,
        document_type: Optional[DocumentType] = None,
        status: Optional[DocumentStatus] = None
    ) -> int:
        """Count OCR results with optional filters."""
        collection = self._get_collection()

        query = {}
        if document_type:
            query["document_type"] = document_type.value
        if status:
            query["status"] = status.value

        return await collection.count_documents(query)

    async def update(self, ocr_id: str, update_data: dict) -> Optional[dict]:
        """Update an OCR result record."""
        collection = self._get_collection()
        update_data["updated_at"] = datetime.utcnow()

        result = await collection.find_one_and_update(
            {"_id": ObjectId(ocr_id)},
            {"$set": update_data},
            return_document=True
        )
        return result

    async def delete(self, ocr_id: str) -> bool:
        """Delete an OCR result record."""
        collection = self._get_collection()
        result = await collection.delete_one({"_id": ObjectId(ocr_id)})
        return result.deleted_count > 0

    async def get_pending_reviews(self, limit: int = 50) -> List[dict]:
        """Get OCR results pending review."""
        collection = self._get_collection()
        cursor = collection.find(
            {"status": DocumentStatus.PENDING_REVIEW.value}
        ).sort("created_at", 1).limit(limit)
        return await cursor.to_list(length=limit)


# Singleton instance
ocr_repository = OCRRepository()


def get_ocr_repository() -> OCRRepository:
    """Get singleton OCR repository instance."""
    return ocr_repository

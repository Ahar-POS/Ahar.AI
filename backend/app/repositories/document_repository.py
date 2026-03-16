"""
Repository for document upload operations.
"""
from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database
from app.models.document import DocumentStatus, DocumentType


class DocumentRepository:
    """Repository for document upload operations."""

    def __init__(self):
        self.collection: AsyncIOMotorCollection = None

    def _get_collection(self) -> AsyncIOMotorCollection:
        """Get document_uploads collection."""
        if self.collection is None:
            db = get_database()
            self.collection = db.document_uploads
        return self.collection

    async def _resolve_uploader_names(self, uploaded_by_ids: List[str]) -> Dict[str, str]:
        """Resolve uploader display names for a list of user IDs."""
        if not uploaded_by_ids:
            return {}

        users_collection = get_database().users
        valid_object_ids: List[ObjectId] = []

        for user_id in uploaded_by_ids:
            try:
                valid_object_ids.append(ObjectId(user_id))
            except Exception:
                continue

        if not valid_object_ids:
            return {}

        cursor = users_collection.find(
            {"_id": {"$in": valid_object_ids}},
            {"first_name": 1, "last_name": 1}
        )

        user_name_map: Dict[str, str] = {}
        async for user in cursor:
            first_name = str(user.get("first_name", "")).strip()
            last_name = str(user.get("last_name", "")).strip()
            full_name = f"{first_name} {last_name}".strip()
            user_name_map[str(user["_id"])] = full_name or str(user["_id"])

        return user_name_map

    async def create(self, document_data: dict) -> dict:
        """Create a new document upload record."""
        collection = self._get_collection()
        document_data["created_at"] = datetime.utcnow()
        document_data["updated_at"] = datetime.utcnow()

        result = await collection.insert_one(document_data)
        created_document = await collection.find_one({"_id": result.inserted_id})
        return created_document

    async def get_by_id(self, document_id: str) -> Optional[dict]:
        """Get document by ID."""
        collection = self._get_collection()
        return await collection.find_one({"_id": ObjectId(document_id)})

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
        document_type: Optional[DocumentType] = None,
        status: Optional[DocumentStatus] = None,
        uploaded_by: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[dict]:
        """Get all documents with optional filters."""
        collection = self._get_collection()

        query = {}
        if document_type:
            query["document_type"] = document_type.value
        if status:
            query["status"] = status.value
        if uploaded_by:
            query["uploaded_by"] = uploaded_by

        # Date range filter
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = datetime.fromisoformat(start_date)
            if end_date:
                date_query["$lte"] = datetime.fromisoformat(end_date)
            query["created_at"] = date_query

        cursor = collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        documents = await cursor.to_list(length=limit)

        uploaded_by_ids = list({
            str(doc.get("uploaded_by", ""))
            for doc in documents
            if doc.get("uploaded_by")
        })
        user_name_map = await self._resolve_uploader_names(uploaded_by_ids)

        for doc in documents:
            uploader_id = str(doc.get("uploaded_by", ""))
            if uploader_id:
                doc["uploaded_by_name"] = user_name_map.get(uploader_id, uploader_id)

        return documents

    async def count(
        self,
        document_type: Optional[DocumentType] = None,
        status: Optional[DocumentStatus] = None,
        uploaded_by: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> int:
        """Count documents with optional filters."""
        collection = self._get_collection()

        query = {}
        if document_type:
            query["document_type"] = document_type.value
        if status:
            query["status"] = status.value
        if uploaded_by:
            query["uploaded_by"] = uploaded_by

        # Date range filter
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = datetime.fromisoformat(start_date)
            if end_date:
                date_query["$lte"] = datetime.fromisoformat(end_date)
            query["created_at"] = date_query

        return await collection.count_documents(query)

    async def update(self, document_id: str, update_data: dict) -> Optional[dict]:
        """Update a document record."""
        collection = self._get_collection()
        update_data["updated_at"] = datetime.utcnow()

        result = await collection.find_one_and_update(
            {"_id": ObjectId(document_id)},
            {"$set": update_data},
            return_document=True
        )
        return result

    async def delete(self, document_id: str) -> bool:
        """Delete a document record."""
        collection = self._get_collection()
        result = await collection.delete_one({"_id": ObjectId(document_id)})
        return result.deleted_count > 0

    async def get_pending_reviews(self, limit: int = 50) -> List[dict]:
        """Get documents pending review."""
        collection = self._get_collection()
        cursor = collection.find(
            {"status": DocumentStatus.PENDING_REVIEW.value}
        ).sort("created_at", 1).limit(limit)
        return await cursor.to_list(length=limit)


# Singleton instance
document_repository = DocumentRepository()


def get_document_repository() -> DocumentRepository:
    """Get singleton document repository instance."""
    return document_repository

"""
Shopping List Repository

Database operations for shopping lists collection.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId

from app.core.database import get_database


class ShoppingListRepository:
    """Repository for shopping list operations"""

    def __init__(self):
        self.db = None
        self.collection_name = "shopping_lists"

    def _get_collection(self):
        """Get MongoDB collection"""
        if self.db is None:
            self.db = get_database()
        return self.db[self.collection_name]

    async def create(self, shopping_list: Dict[str, Any]) -> str:
        """
        Create a new shopping list

        Args:
            shopping_list: Shopping list document

        Returns:
            Inserted document ID
        """
        collection = self._get_collection()
        result = await collection.insert_one(shopping_list)
        return str(result.inserted_id)

    async def get_by_id(self, list_id: str) -> Optional[Dict]:
        """
        Get shopping list by MongoDB ID

        Args:
            list_id: MongoDB ObjectId string

        Returns:
            Shopping list document or None
        """
        collection = self._get_collection()
        shopping_list = await collection.find_one({"_id": ObjectId(list_id)})

        if shopping_list:
            shopping_list["_id"] = str(shopping_list["_id"])
            if "agent_decision_id" in shopping_list:
                shopping_list["agent_decision_id"] = str(shopping_list["agent_decision_id"])

        return shopping_list

    async def get_by_list_id(self, list_id: str) -> Optional[Dict]:
        """
        Get shopping list by list_id (e.g., "SL_2026-02-24")

        Args:
            list_id: List identifier string

        Returns:
            Shopping list document or None
        """
        collection = self._get_collection()
        shopping_list = await collection.find_one({"list_id": list_id})

        if shopping_list:
            shopping_list["_id"] = str(shopping_list["_id"])
            if "agent_decision_id" in shopping_list:
                shopping_list["agent_decision_id"] = str(shopping_list["agent_decision_id"])

        return shopping_list

    async def get_by_status(
        self,
        status: str,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict]:
        """
        Get shopping lists by status

        Args:
            status: Status filter (pending, approved, rejected, partially_approved)
            limit: Maximum results
            skip: Skip first N results (for pagination)

        Returns:
            List of shopping list documents
        """
        collection = self._get_collection()
        cursor = collection.find({"status": status}).sort("generated_at", -1).skip(skip).limit(limit)
        lists = await cursor.to_list(length=limit)

        for lst in lists:
            lst["_id"] = str(lst["_id"])
            if "agent_decision_id" in lst:
                lst["agent_decision_id"] = str(lst["agent_decision_id"])

        return lists

    async def get_all(
        self,
        limit: int = 50,
        skip: int = 0,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all shopping lists

        Args:
            limit: Maximum results
            skip: Skip first N results
            status: Optional status filter

        Returns:
            List of shopping list documents
        """
        collection = self._get_collection()

        query = {}
        if status:
            query["status"] = status

        cursor = collection.find(query).sort("generated_at", -1).skip(skip).limit(limit)
        lists = await cursor.to_list(length=limit)

        for lst in lists:
            lst["_id"] = str(lst["_id"])
            if "agent_decision_id" in lst:
                lst["agent_decision_id"] = str(lst["agent_decision_id"])

        return lists

    async def count_by_status(self, status: Optional[str] = None) -> int:
        """
        Count shopping lists by status

        Args:
            status: Optional status filter

        Returns:
            Count of documents
        """
        collection = self._get_collection()

        query = {}
        if status:
            query["status"] = status

        return await collection.count_documents(query)

    async def update_status(
        self,
        list_id: str,
        status: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Update shopping list status

        Args:
            list_id: MongoDB ObjectId string
            status: New status (approved, rejected, partially_approved)
            user_id: User who performed action
            notes: Optional approval/rejection notes

        Returns:
            True if updated, False if not found
        """
        collection = self._get_collection()

        result = await collection.update_one(
            {"_id": ObjectId(list_id)},
            {
                "$set": {
                    "status": status,
                    "reviewed_at": datetime.utcnow(),
                    "reviewed_by": user_id,
                    "approval_notes": notes
                }
            }
        )

        return result.modified_count > 0

    async def approve_items(
        self,
        list_id: str,
        material_ids: List[str],
        user_id: str
    ) -> bool:
        """
        Approve specific items in shopping list (partial approval)

        Args:
            list_id: MongoDB ObjectId string
            material_ids: List of material IDs to approve
            user_id: User who approved

        Returns:
            True if updated, False if not found
        """
        collection = self._get_collection()

        # Update individual items
        await collection.update_one(
            {"_id": ObjectId(list_id)},
            {
                "$set": {
                    "items.$[elem].item_status": "approved",
                    "items.$[elem].approved_at": datetime.utcnow(),
                    "items.$[elem].approved_by": user_id
                }
            },
            array_filters=[{"elem.material_id": {"$in": material_ids}}]
        )

        # Update list status to partially_approved
        result = await collection.update_one(
            {"_id": ObjectId(list_id)},
            {
                "$set": {
                    "status": "partially_approved",
                    "reviewed_at": datetime.utcnow(),
                    "reviewed_by": user_id
                }
            }
        )

        return result.modified_count > 0

    async def update(
        self,
        list_id: str,
        update_data: Dict[str, Any]
    ) -> bool:
        """
        Update shopping list fields

        Args:
            list_id: MongoDB ObjectId string
            update_data: Fields to update

        Returns:
            True if updated, False if not found
        """
        collection = self._get_collection()

        result = await collection.update_one(
            {"_id": ObjectId(list_id)},
            {"$set": update_data}
        )

        return result.modified_count > 0

    async def delete(self, list_id: str) -> bool:
        """
        Delete shopping list

        Args:
            list_id: MongoDB ObjectId string

        Returns:
            True if deleted, False if not found
        """
        collection = self._get_collection()
        result = await collection.delete_one({"_id": ObjectId(list_id)})
        return result.deleted_count > 0


# Singleton
_shopping_list_repository = None


def get_shopping_list_repository() -> ShoppingListRepository:
    """Get singleton shopping list repository instance"""
    global _shopping_list_repository
    if _shopping_list_repository is None:
        _shopping_list_repository = ShoppingListRepository()
    return _shopping_list_repository

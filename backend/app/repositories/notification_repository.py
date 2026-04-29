from datetime import datetime
from app.utils.timezone import now_ist
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database


class NotificationRepository:
    """MongoDB operations for the notifications collection."""

    def __init__(self):
        self._collection: Optional[AsyncIOMotorCollection] = None

    def _col(self) -> AsyncIOMotorCollection:
        if self._collection is None:
            self._collection = get_database().notifications
        return self._collection

    async def create(self, doc: dict) -> dict:
        result = await self._col().insert_one(doc)
        return await self._col().find_one({"_id": result.inserted_id})

    async def get_for_role(
        self,
        role: str,
        page: int = 1,
        limit: int = 20,
        unread_only: bool = False,
    ) -> List[dict]:
        query: dict = {"target_roles": role}
        if unread_only:
            query["is_read"] = False
        skip = (page - 1) * limit
        cursor = (
            self._col()
            .find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def count_for_role(
        self,
        role: str,
        unread_only: bool = False,
    ) -> int:
        query: dict = {"target_roles": role}
        if unread_only:
            query["is_read"] = False
        return await self._col().count_documents(query)

    async def get_unread_count(self, role: str) -> int:
        return await self.count_for_role(role, unread_only=True)

    async def mark_read(self, notification_id: str, role: str) -> bool:
        result = await self._col().update_one(
            {"notification_id": notification_id, "target_roles": role, "is_read": False},
            {"$set": {"is_read": True, "read_at": now_ist()}},
        )
        return result.modified_count > 0

    async def mark_all_read(self, role: str) -> int:
        result = await self._col().update_many(
            {"target_roles": role, "is_read": False},
            {"$set": {"is_read": True, "read_at": now_ist()}},
        )
        return result.modified_count


_instance: Optional[NotificationRepository] = None


def get_notification_repository() -> NotificationRepository:
    global _instance
    if _instance is None:
        _instance = NotificationRepository()
    return _instance

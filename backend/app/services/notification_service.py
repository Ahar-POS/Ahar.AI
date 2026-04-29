"""
Notification Service — create and query in-app notifications.

Called by the orchestrator when agents fire events.
Also called directly by Phase 3 (expiry) and Phase 5 (approval thresholds).
"""
import uuid
import logging
from datetime import datetime
from app.utils.timezone import now_ist
from typing import List, Optional, Dict, Any

from app.repositories.notification_repository import get_notification_repository

logger = logging.getLogger(__name__)

RESTAURANT_ID = "antera_jubilee_hills"


class NotificationService:

    def __init__(self):
        self._repo = get_notification_repository()

    async def create_notification(
        self,
        type: str,
        title: str,
        message: str,
        severity: str,
        target_roles: List[str],
        metadata: Optional[Dict[str, Any]] = None,
        restaurant_id: str = RESTAURANT_ID,
    ) -> str:
        """Create a notification and return its notification_id."""
        notification_id = f"NOTIF_{uuid.uuid4().hex[:12].upper()}"
        doc = {
            "notification_id": notification_id,
            "type": type,
            "title": title,
            "message": message,
            "severity": severity,
            "target_roles": target_roles,
            "restaurant_id": restaurant_id,
            "metadata": metadata or {},
            "is_read": False,
            "read_at": None,
            "created_at": now_ist(),
        }
        await self._repo.create(doc)
        logger.info(f"Created notification {notification_id} type={type} roles={target_roles}")
        return notification_id

    async def get_notifications(
        self,
        role: str,
        page: int = 1,
        limit: int = 20,
        unread_only: bool = False,
    ) -> tuple[List[dict], int]:
        """Return (items, total) for the given role."""
        items = await self._repo.get_for_role(role, page, limit, unread_only)
        total = await self._repo.count_for_role(role, unread_only)
        return items, total

    async def get_unread_count(self, role: str) -> int:
        return await self._repo.get_unread_count(role)

    async def mark_read(self, notification_id: str, role: str) -> bool:
        return await self._repo.mark_read(notification_id, role)

    async def mark_all_read(self, role: str) -> int:
        return await self._repo.mark_all_read(role)


_instance: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    global _instance
    if _instance is None:
        _instance = NotificationService()
    return _instance

"""
Shopping List Service

Business logic for shopping list management and approval workflow.

Responsibilities:
- Create shopping lists from agent decisions
- Approval workflow (approve/reject/partial)
- Status tracking
- Supplier grouping
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.repositories.shopping_list_repository import get_shopping_list_repository

logger = logging.getLogger(__name__)


class ShoppingListService:
    """Service for managing shopping lists"""

    def __init__(self):
        self.repository = get_shopping_list_repository()

    async def create_shopping_list(
        self,
        items: List[Dict[str, Any]],
        agent_decision_id: str,
        reasoning: str,
        confidence: float
    ) -> str:
        """
        Create a new shopping list

        Args:
            items: List of items to purchase
            agent_decision_id: Link to agent_decisions collection
            reasoning: Agent reasoning
            confidence: Confidence score

        Returns:
            Shopping list MongoDB ID
        """
        logger.info(f"Creating shopping list with {len(items)} items")

        # Calculate total cost
        total_cost_inr = sum(
            item.get("line_total_inr", item.get("quantity_to_order", 0) * item.get("unit_cost_inr", 0))
            for item in items
        )

        # Group by urgency
        urgency_summary = {
            "urgent_count": sum(1 for i in items if i.get("urgency") == "URGENT"),
            "standard_count": sum(1 for i in items if i.get("urgency") == "STANDARD"),
            "low_priority_count": sum(1 for i in items if i.get("urgency") == "LOW_PRIORITY")
        }

        # Group by supplier
        supplier_breakdown = self._group_by_supplier(items)

        # Generate list_id
        list_id = f"SL_{datetime.utcnow().strftime('%Y-%m-%d_%H%M%S')}"

        # Create shopping list document
        shopping_list = {
            "list_id": list_id,
            "generated_at": datetime.utcnow(),
            "generated_by": "inventory_agent",
            "status": "pending",
            "urgency_summary": urgency_summary,
            "total_cost_inr": total_cost_inr,
            "estimated_total": total_cost_inr,
            "items": items,
            "supplier_breakdown": supplier_breakdown,
            "agent_decision_id": agent_decision_id,
            "confidence_score": confidence,
            "reasoning": reasoning,
            "reviewed_at": None,
            "reviewed_by": None,
            "approval_notes": None,
            "executed_at": None,
            "execution_status": "pending",
            "execution_notes": None
        }

        # Insert to database
        mongo_id = await self.repository.create(shopping_list)

        logger.info(
            f"Created shopping list {list_id} (ID: {mongo_id}): "
            f"{len(items)} items, ₹{total_cost_inr/100:.2f}, "
            f"{urgency_summary['urgent_count']} URGENT"
        )

        return mongo_id

    def _group_by_supplier(self, items: List[Dict]) -> List[Dict]:
        """
        Group items by supplier for easier ordering

        Args:
            items: Shopping list items

        Returns:
            List of supplier summaries
        """
        supplier_map = {}

        for item in items:
            supplier_id = item.get("supplier_id", "UNKNOWN")

            if supplier_id not in supplier_map:
                supplier_map[supplier_id] = {
                    "supplier_id": supplier_id,
                    "supplier_name": item.get("supplier_name", "Unknown Supplier"),
                    "item_count": 0,
                    "total_cost_inr": 0,
                    "items": []
                }

            supplier_map[supplier_id]["item_count"] += 1
            supplier_map[supplier_id]["total_cost_inr"] += item.get("line_total_inr", 0)
            supplier_map[supplier_id]["items"].append(item.get("material_id", ""))

        return list(supplier_map.values())

    async def get_pending_shopping_lists(self) -> List[Dict]:
        """
        Get all pending shopping lists

        Returns:
            List of pending shopping lists
        """
        return await self.repository.get_by_status("pending", limit=100)

    async def get_shopping_list(self, list_id: str) -> Optional[Dict]:
        """
        Get shopping list by ID

        Args:
            list_id: MongoDB ObjectId string

        Returns:
            Shopping list document or None
        """
        return await self.repository.get_by_id(list_id)

    async def approve_list(
        self,
        list_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Approve entire shopping list

        Args:
            list_id: MongoDB ObjectId string
            user_id: User who approved
            notes: Optional approval notes

        Returns:
            True if approved, False if not found
        """
        logger.info(f"Approving shopping list {list_id} by user {user_id}")

        success = await self.repository.update_status(
            list_id,
            status="approved",
            user_id=user_id,
            notes=notes
        )

        if success:
            logger.info(f"Shopping list {list_id} approved successfully")
        else:
            logger.warning(f"Failed to approve shopping list {list_id} (not found or already processed)")

        return success

    async def approve_items(
        self,
        list_id: str,
        material_ids: List[str],
        user_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Approve specific items in shopping list (partial approval)

        Args:
            list_id: MongoDB ObjectId string
            material_ids: List of material IDs to approve
            user_id: User who approved
            notes: Optional approval notes

        Returns:
            True if approved, False if not found
        """
        logger.info(
            f"Partially approving shopping list {list_id}: "
            f"{len(material_ids)} items by user {user_id}"
        )

        success = await self.repository.approve_items(
            list_id,
            material_ids,
            user_id
        )

        # Update approval notes if provided
        if success and notes:
            await self.repository.update(
                list_id,
                {"approval_notes": notes}
            )

        if success:
            logger.info(
                f"Shopping list {list_id} partially approved: "
                f"{len(material_ids)} items"
            )
        else:
            logger.warning(f"Failed to partially approve shopping list {list_id}")

        return success

    async def reject_list(
        self,
        list_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Reject shopping list

        Args:
            list_id: MongoDB ObjectId string
            user_id: User who rejected
            notes: Optional rejection notes

        Returns:
            True if rejected, False if not found
        """
        logger.info(f"Rejecting shopping list {list_id} by user {user_id}")

        success = await self.repository.update_status(
            list_id,
            status="rejected",
            user_id=user_id,
            notes=notes
        )

        if success:
            logger.info(f"Shopping list {list_id} rejected")
        else:
            logger.warning(f"Failed to reject shopping list {list_id}")

        return success

    async def get_approval_history(
        self,
        limit: int = 50,
        skip: int = 0,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Get approval history audit log

        Args:
            limit: Maximum results
            skip: Skip first N results (pagination)
            status: Optional status filter

        Returns:
            List of shopping lists
        """
        return await self.repository.get_all(
            limit=limit,
            skip=skip,
            status=status
        )

    async def count_by_status(self, status: Optional[str] = None) -> int:
        """
        Count shopping lists by status

        Args:
            status: Optional status filter

        Returns:
            Count of shopping lists
        """
        return await self.repository.count_by_status(status)


# Singleton
_shopping_list_service = None


def get_shopping_list_service() -> ShoppingListService:
    """Get singleton shopping list service instance"""
    global _shopping_list_service
    if _shopping_list_service is None:
        _shopping_list_service = ShoppingListService()
    return _shopping_list_service

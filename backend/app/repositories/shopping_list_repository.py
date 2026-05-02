"""
Shopping List Repository

Database operations for shopping lists collection.
"""

from datetime import datetime
from app.utils.timezone import now_ist
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
                    "reviewed_at": now_ist(),
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
                    "items.$[elem].approved_at": now_ist(),
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
                    "reviewed_at": now_ist(),
                    "reviewed_by": user_id
                }
            }
        )

        return result.modified_count > 0

    async def review_items(
        self,
        list_id: str,
        item_decisions: List[Dict[str, Any]],
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Apply per-item approve/reject decisions (Option B partial approval model).

        Each decision dict has: material_id, action ("approve"|"reject"),
        quantity (for approve), reason (for reject).

        Partial submissions are valid — items not in this list keep their current status.

        Args:
            list_id: MongoDB ObjectId string
            item_decisions: List of per-item decision dicts
            user_id: User making the decisions

        Returns:
            Summary dict with counts and list_status, or None if list not found
        """
        collection = self._get_collection()
        now = now_ist()

        # Apply each item decision individually
        for decision in item_decisions:
            material_id = decision["material_id"]
            action = decision["action"]

            if action == "approve":
                update_fields = {
                    "items.$[elem].item_status": "approved",
                    "items.$[elem].approved_quantity": decision.get("quantity"),
                    "items.$[elem].rejection_reason": None,
                    "items.$[elem].decided_at": now,
                    "items.$[elem].decided_by": user_id,
                }
            else:
                update_fields = {
                    "items.$[elem].item_status": "rejected",
                    "items.$[elem].approved_quantity": 0,
                    "items.$[elem].rejection_reason": decision.get("reason"),
                    "items.$[elem].decided_at": now,
                    "items.$[elem].decided_by": user_id,
                }

            await collection.update_one(
                {"_id": ObjectId(list_id)},
                {"$set": update_fields},
                array_filters=[{"elem.material_id": material_id}]
            )

        # Re-fetch to compute list-level status from updated items
        doc = await collection.find_one({"_id": ObjectId(list_id)})
        if not doc:
            return None

        items = doc.get("items", [])
        approved = sum(1 for i in items if i.get("item_status") == "approved")
        rejected = sum(1 for i in items if i.get("item_status") == "rejected")
        pending = sum(1 for i in items if i.get("item_status") not in ("approved", "rejected"))
        total = len(items)

        if pending > 0:
            list_status = "partially_approved"
        elif approved == total:
            list_status = "approved"
        elif rejected == total:
            list_status = "rejected"
        else:
            list_status = "partially_approved"

        await collection.update_one(
            {"_id": ObjectId(list_id)},
            {"$set": {
                "status": list_status,
                "reviewed_at": now,
                "reviewed_by": user_id
            }}
        )

        approved_total_paise = sum(
            (i.get("approved_quantity") or 0) * i.get("unit_cost_inr", 0)
            for i in items
            if i.get("item_status") == "approved"
        )

        return {
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "total": total,
            "list_status": list_status,
            "approved_total_paise": int(approved_total_paise),
        }

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

    async def get_active_list(self) -> Optional[Dict]:
        """
        Get the single active shopping list (pending or partially_approved).
        Returns the most recent one if multiple exist (shouldn't happen in practice).
        """
        collection = self._get_collection()
        doc = await collection.find_one(
            {"status": {"$in": ["pending", "partially_approved"]}},
            sort=[("generated_at", -1)]
        )
        if doc:
            doc["_id"] = str(doc["_id"])
            if "agent_decision_id" in doc:
                doc["agent_decision_id"] = str(doc["agent_decision_id"])
        return doc

    async def upsert_items(
        self,
        list_id: str,
        new_items: List[Dict[str, Any]],
        agent_decision_id: str,
        reasoning: str,
        confidence: float
    ) -> bool:
        """
        Upsert items into an existing active shopping list.

        - Items with item_status in (pending_review, auto_approved) are overwritten with IA's latest qty/urgency.
        - Items with item_status in (owner_approved, owner_rejected, ordered, delivered) are preserved as-is.
        - New material_ids are appended.

        Returns True if updated.
        """
        collection = self._get_collection()
        doc = await collection.find_one({"_id": ObjectId(list_id)})
        if not doc:
            return False

        existing_items = doc.get("items", [])
        # Index existing items by material_id
        existing_map = {i["material_id"]: i for i in existing_items}
        locked_statuses = {"owner_approved", "owner_rejected", "ordered", "delivered"}
        now = now_ist()

        merged = []
        for item in new_items:
            mid = item["material_id"]
            if mid in existing_map:
                existing = existing_map[mid]
                if existing.get("item_status") in locked_statuses:
                    # Preserve locked items unchanged
                    merged.append(existing)
                else:
                    # Overwrite mutable fields with IA's latest recommendation
                    existing.update({
                        "quantity_to_order": item.get("quantity_to_order", existing.get("quantity_to_order")),
                        "unit_cost_inr": item.get("unit_cost_inr", existing.get("unit_cost_inr")),
                        "line_total_inr": item.get("line_total_inr", existing.get("line_total_inr")),
                        "urgency": item.get("urgency", existing.get("urgency")),
                        "item_status": item.get("item_status", existing.get("item_status")),
                        "last_updated_at": now,
                    })
                    merged.append(existing)
                del existing_map[mid]
            else:
                # New item from IA — start as pending_review
                item.setdefault("item_status", "pending_review")
                item["last_updated_at"] = now
                merged.append(item)

        # Preserve any remaining locked items not in new_items
        for mid, item in existing_map.items():
            if item.get("item_status") in locked_statuses:
                merged.append(item)

        total_cost_inr = sum(i.get("line_total_inr", 0) for i in merged)
        urgency_summary = {
            "urgent_count": sum(1 for i in merged if i.get("urgency") == "URGENT"),
            "standard_count": sum(1 for i in merged if i.get("urgency") == "STANDARD"),
            "low_priority_count": sum(1 for i in merged if i.get("urgency") == "LOW_PRIORITY"),
        }

        result = await collection.update_one(
            {"_id": ObjectId(list_id)},
            {"$set": {
                "items": merged,
                "total_cost_inr": total_cost_inr,
                "estimated_total": total_cost_inr,
                "urgency_summary": urgency_summary,
                "agent_decision_id": ObjectId(agent_decision_id),
                "confidence_score": confidence,
                "reasoning": reasoning,
                "last_updated_at": now,
            }}
        )
        return result.modified_count > 0

    async def mark_items_ordered(self, list_id: str, material_ids: List[str], po_id: str) -> bool:
        """Mark items as ordered after Hyperpure placement."""
        collection = self._get_collection()
        now = now_ist()
        await collection.update_one(
            {"_id": ObjectId(list_id)},
            {
                "$set": {
                    "items.$[elem].item_status": "ordered",
                    "items.$[elem].po_id": po_id,
                    "items.$[elem].ordered_at": now,
                }
            },
            array_filters=[{"elem.material_id": {"$in": material_ids}}]
        )
        # If all items are ordered/delivered, archive the list
        doc = await collection.find_one({"_id": ObjectId(list_id)})
        if doc:
            items = doc.get("items", [])
            actionable = [i for i in items if i.get("item_status") not in ("owner_rejected",)]
            all_done = all(i.get("item_status") in ("ordered", "delivered") for i in actionable)
            if all_done:
                await collection.update_one(
                    {"_id": ObjectId(list_id)},
                    {"$set": {"status": "completed", "executed_at": now}}
                )
        return True

    async def mark_items_delivered(self, list_id: str, material_ids: List[str]) -> bool:
        """Mark items as delivered after staff confirms receipt."""
        collection = self._get_collection()
        now = now_ist()
        await collection.update_one(
            {"_id": ObjectId(list_id)},
            {
                "$set": {
                    "items.$[elem].item_status": "delivered",
                    "items.$[elem].delivered_at": now,
                }
            },
            array_filters=[{"elem.material_id": {"$in": material_ids}}]
        )
        return True

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

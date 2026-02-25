from datetime import datetime
from typing import List, Optional
from bson import ObjectId

from app.repositories.inventory_repository import inventory_repository
from app.models.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse
)


class InventoryService:
    """Service for inventory business logic"""

    async def create_item(self, item_data: InventoryItemCreate) -> InventoryItemResponse:
        """Create a new inventory item"""
        # Check if material_id already exists
        existing = await inventory_repository.get_by_material_id(item_data.material_id)
        if existing:
            raise ValueError(f"Material ID {item_data.material_id} already exists")

        item_dict = item_data.model_dump()
        created_item = await inventory_repository.create(item_dict)

        return self._format_item_response(created_item)

    async def get_item(self, item_id: str) -> Optional[InventoryItemResponse]:
        """Get inventory item by ID"""
        item = await inventory_repository.get_by_id(item_id)
        if not item:
            return None

        return self._format_item_response(item)

    async def get_all_items(
        self,
        page: int = 1,
        limit: int = 20,
        category: Optional[str] = None,
        is_perishable: Optional[str] = None
    ) -> tuple[List[InventoryItemResponse], int]:
        """Get all inventory items with pagination"""
        skip = (page - 1) * limit

        items = await inventory_repository.get_all(
            skip=skip,
            limit=limit,
            category=category,
            is_perishable=is_perishable
        )

        total = await inventory_repository.count(
            category=category,
            is_perishable=is_perishable
        )

        items_response = [self._format_item_response(item) for item in items]
        return items_response, total

    async def update_item(
        self,
        item_id: str,
        update_data: InventoryItemUpdate
    ) -> Optional[InventoryItemResponse]:
        """Update an inventory item"""
        # Check if item exists
        existing = await inventory_repository.get_by_id(item_id)
        if not existing:
            return None

        # Only update provided fields
        update_dict = update_data.model_dump(exclude_unset=True)
        if not update_dict:
            return self._format_item_response(existing)

        updated_item = await inventory_repository.update(item_id, update_dict)
        return self._format_item_response(updated_item)

    async def delete_item(self, item_id: str) -> bool:
        """Delete an inventory item"""
        return await inventory_repository.delete(item_id)

    async def get_low_stock_items(self) -> List[InventoryItemResponse]:
        """Get items that need restocking"""
        items = await inventory_repository.get_low_stock_items()
        return [self._format_item_response(item) for item in items]

    async def search_items_by_name(self, query: str) -> List[InventoryItemResponse]:
        """Search inventory items by name substring"""
        items = await inventory_repository.search_by_name(query)
        return [self._format_item_response(item) for item in items]

    async def bulk_import_items(self, items: List[InventoryItemCreate]) -> int:
        """Bulk import inventory items"""
        items_dict = [item.model_dump() for item in items]
        count = await inventory_repository.bulk_create(items_dict)
        return count

    def _format_item_response(self, item: dict) -> InventoryItemResponse:
        """Format database item to response model, coercing types for imported/legacy data."""
        item = dict(item)
        item["_id"] = str(item.get("_id", ""))

        # Integer fields: DB may store floats (e.g. from analytics); coerce to int
        int_fields = (
            "unit_cost_inr", "reorder_level", "reorder_qty", "current_stock",
            "max_stock", "lead_time_days", "shelf_life_days"
        )
        for key in int_fields:
            if key in item and item[key] is not None:
                val = item[key]
                if isinstance(val, float):
                    item[key] = int(round(val))
                elif not isinstance(val, int):
                    try:
                        item[key] = int(float(val))
                    except (TypeError, ValueError):
                        pass

        # last_restock_date: DB may have datetime; response expects str or None
        val = item.get("last_restock_date")
        if val is None:
            item["last_restock_date"] = None
        elif isinstance(val, datetime):
            item["last_restock_date"] = val.date().isoformat() if hasattr(val, "date") else val.isoformat()
        else:
            item["last_restock_date"] = str(val) if val else None

        # storage_temp_c: DB may have int/float (e.g. 4); response expects str
        val = item.get("storage_temp_c")
        if val is None:
            item["storage_temp_c"] = ""
        elif isinstance(val, (int, float)):
            item["storage_temp_c"] = str(int(val)) if isinstance(val, float) else str(val)
        else:
            item["storage_temp_c"] = str(val)

        # is_perishable: DB may have bool; response expects str (Yes/No)
        val = item.get("is_perishable")
        if val is None:
            item["is_perishable"] = "No"
        elif isinstance(val, bool):
            item["is_perishable"] = "Yes" if val else "No"
        else:
            item["is_perishable"] = str(val).strip() or "No"

        return InventoryItemResponse(**item)


inventory_service = InventoryService()

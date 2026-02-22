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
        """Format database item to response model"""
        item["_id"] = str(item["_id"])
        return InventoryItemResponse(**item)


inventory_service = InventoryService()

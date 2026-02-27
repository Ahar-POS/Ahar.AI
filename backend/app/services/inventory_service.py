from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId
import logging

from app.repositories.inventory_repository import inventory_repository
from app.repositories.recipe_repository import get_recipe_repository
from app.models.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse
)
from app.models.inventory_consumption import InventoryConsumption, ConsumedMaterial
from app.core.database import get_database

logger = logging.getLogger(__name__)


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

    async def consume_for_order(
        self,
        order_items: List[Dict[str, Any]],
        order_id: Optional[str] = None,
        order_number: Optional[int] = None,
        restaurant_id: Optional[str] = None,
        check_stock: bool = False
    ) -> Dict[str, Any]:
        """
        Consume inventory for completed order.

        Args:
            order_items: List of order items with menu_item_id (MongoDB _id) and quantity
            check_stock: If True, check for sufficient stock before deducting

        Returns:
            Dict with:
                - success: bool
                - consumed: List of materials consumed with quantities
                - warnings: List of low/negative stock warnings
                - errors: List of errors (e.g., missing recipes)

        Example:
            order_items = [
                {"menu_item_id": "699c76b6bdcd72438d001aee", "quantity": 2},
                {"menu_item_id": "699c76b6bdcd72438d001af0", "quantity": 1}
            ]
        """
        recipe_repo = get_recipe_repository()
        consumed = []
        warnings = []
        errors = []

        # Aggregate ingredient requirements across all items
        ingredient_totals: Dict[str, float] = {}

        for order_item in order_items:
            menu_item_object_id = order_item.get("menu_item_id")
            order_qty = order_item.get("quantity", 1)

            # First, get the menu item to retrieve its string menu_item_id
            db = get_database()
            menu_item = await db.menu_items.find_one({"_id": ObjectId(menu_item_object_id)})

            if not menu_item:
                errors.append(f"Menu item not found: {menu_item_object_id}")
                logger.warning(f"Menu item not found: {menu_item_object_id}")
                continue

            # Get the string menu_item_id (e.g., "MENU001")
            menu_item_id = menu_item.get("menu_item_id")

            if not menu_item_id:
                errors.append(f"Menu item missing menu_item_id field: {menu_item_object_id}")
                logger.warning(f"Menu item {menu_item_object_id} missing menu_item_id field")
                continue

            # Get recipe for this menu item using the string ID
            recipe = await recipe_repo.get_by_menu_item(menu_item_id)

            if not recipe:
                errors.append(f"No recipe found for menu item: {menu_item_id} (name: {menu_item.get('name', 'Unknown')})")
                logger.warning(f"No recipe found for menu item {menu_item_id}")
                continue

            # Aggregate ingredients
            for ingredient in recipe.get("ingredients", []):
                material_id = ingredient["material_id"]
                qty_per_serving = ingredient["quantity_per_serving"]
                total_qty = qty_per_serving * order_qty

                if material_id in ingredient_totals:
                    ingredient_totals[material_id] += total_qty
                else:
                    ingredient_totals[material_id] = total_qty

        # Check stock levels if requested
        if check_stock:
            for material_id, quantity in ingredient_totals.items():
                item = await inventory_repository.get_by_material_id(material_id)
                if item:
                    current_stock = item.get("current_stock", 0)
                    if current_stock < quantity:
                        warnings.append(
                            f"{item['material_name']} ({material_id}): "
                            f"Insufficient stock. Have {current_stock}, need {quantity}"
                        )

        # Deduct stock
        decrements = [
            {"material_id": material_id, "quantity": quantity}
            for material_id, quantity in ingredient_totals.items()
        ]

        updated_count = await inventory_repository.bulk_decrement_stock(decrements)

        # Build consumed list with details
        for material_id, quantity in ingredient_totals.items():
            item = await inventory_repository.get_by_material_id(material_id)
            consumed.append({
                "material_id": material_id,
                "material_name": item["material_name"] if item else "Unknown",
                "quantity": quantity,
                "unit": item["unit"] if item else "",
                "remaining_stock": item["current_stock"] if item else 0
            })

            # Check if stock is now negative or below reorder level
            if item:
                current_stock = item.get("current_stock", 0)
                reorder_level = item.get("reorder_level", 0)

                if current_stock < 0:
                    warnings.append(
                        f"NEGATIVE STOCK: {item['material_name']} ({material_id}) "
                        f"now has {current_stock} {item['unit']}"
                    )
                elif current_stock <= reorder_level:
                    warnings.append(
                        f"LOW STOCK: {item['material_name']} ({material_id}) "
                        f"at {current_stock} {item['unit']} (reorder at {reorder_level})"
                    )

        logger.info(
            f"Consumed inventory for order: {len(consumed)} materials, "
            f"{len(warnings)} warnings, {len(errors)} errors"
        )

        # Log consumption to database if order details provided
        if order_id and order_number and restaurant_id:
            try:
                db = get_database()
                consumption_log = InventoryConsumption(
                    order_id=order_id,
                    order_number=order_number,
                    restaurant_id=restaurant_id,
                    consumed_materials=[
                        ConsumedMaterial(
                            material_id=c["material_id"],
                            material_name=c["material_name"],
                            quantity=c["quantity"],
                            unit=c["unit"],
                            cost_per_unit=0  # Can be enhanced to fetch actual cost
                        )
                        for c in consumed
                    ],
                    total_cost=0,  # Can be calculated from unit costs
                    warnings=warnings,
                    errors=errors,
                    consumed_at=datetime.utcnow()
                )

                await db.inventory_consumption_logs.insert_one(
                    consumption_log.model_dump(by_alias=True, exclude={"id"})
                )

                logger.info(f"Logged consumption for order {order_number}")

            except Exception as e:
                logger.error(f"Failed to log consumption: {e}", exc_info=True)

        return {
            "success": len(errors) == 0,
            "consumed": consumed,
            "warnings": warnings,
            "errors": errors
        }


inventory_service = InventoryService()

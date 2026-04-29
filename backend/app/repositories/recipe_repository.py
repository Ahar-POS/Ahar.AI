"""
Recipe Repository

Handles CRUD operations for recipe_bom collection.
Maps menu items to their ingredient requirements.
"""

from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
from app.utils.timezone import now_ist

from app.core.database import get_database


class RecipeRepository:
    """Repository for recipe bill of materials (BOM)"""

    def __init__(self):
        self.db = None
        self.collection_name = "recipe_bom"

    async def _get_collection(self):
        """Get MongoDB collection"""
        if self.db is None:
            self.db = get_database()
        return self.db[self.collection_name]

    async def get_by_menu_item(self, menu_item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get recipe by menu item ID.

        recipe_bom.menu_item_id stores the ObjectId string of the menu item,
        not the human-readable code (e.g. "MENU070"). Resolve via menu_items first.
        """
        collection = await self._get_collection()

        # Try direct lookup first (handles ObjectId strings passed directly)
        recipe = await collection.find_one({"menu_item_id": menu_item_id})

        if not recipe:
            # Resolve human-readable code → ObjectId via menu_items collection
            menu_item = await self.db["menu_items"].find_one({"menu_item_id": menu_item_id})
            if menu_item:
                recipe = await collection.find_one({"menu_item_id": str(menu_item["_id"])})

        if recipe:
            recipe["id"] = str(recipe.pop("_id"))

        return recipe

    async def get_by_ingredient(self, material_id: str) -> List[Dict[str, Any]]:
        """
        Get all recipes that use a specific ingredient

        Args:
            material_id: Raw material identifier (e.g., "RM001")

        Returns:
            List of recipe documents containing this ingredient
        """
        collection = await self._get_collection()
        cursor = collection.find({"ingredients.material_id": material_id})
        recipes = await cursor.to_list(length=None)

        for recipe in recipes:
            recipe["id"] = str(recipe.pop("_id"))

        return recipes

    async def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all recipes

        Returns:
            List of all recipe documents
        """
        collection = await self._get_collection()
        cursor = collection.find({})
        recipes = await cursor.to_list(length=None)

        for recipe in recipes:
            recipe["id"] = str(recipe.pop("_id"))

        return recipes

    async def get_ingredient_usage_map(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Build a complete map of ingredients to their recipe usage

        Returns:
            Dict mapping material_id to list of recipes using it
            Example: {
                "RM001": [
                    {
                        "menu_item_id": "MENU001",
                        "menu_item_name": "Smoky Chicken Burger",
                        "quantity_per_serving": 140,
                        "unit": "Gram",
                        "is_critical": True
                    }
                ]
            }
        """
        collection = await self._get_collection()
        recipes = await collection.find({}).to_list(length=None)

        ingredient_map: Dict[str, List[Dict[str, Any]]] = {}

        for recipe in recipes:
            for ingredient in recipe.get("ingredients", []):
                material_id = ingredient["material_id"]

                if material_id not in ingredient_map:
                    ingredient_map[material_id] = []

                ingredient_map[material_id].append({
                    "menu_item_id": recipe["menu_item_id"],
                    "menu_item_name": recipe["menu_item_name"],
                    "quantity_per_serving": ingredient["quantity_per_serving"],
                    "unit": ingredient["unit"],
                    "is_critical": ingredient["is_critical"]
                })

        return ingredient_map

    async def get_menu_item_cost(self, menu_item_id: str) -> Optional[float]:
        """
        Calculate raw material cost for a menu item

        Args:
            menu_item_id: Menu item identifier

        Returns:
            Total ingredient cost in paise, or None if recipe not found
        """
        recipe = await self.get_by_menu_item(menu_item_id)
        if not recipe:
            return None

        # Get inventory for cost lookup
        inventory_collection = self.db["raw_material_inventory"]
        total_cost = 0.0

        for ingredient in recipe.get("ingredients", []):
            material = await inventory_collection.find_one(
                {"material_id": ingredient["material_id"]}
            )

            if material:
                # unit_cost_inr is cost per unit (gram/ml/piece)
                quantity = ingredient["quantity_per_serving"]
                unit_cost = material.get("unit_cost_inr", 0)
                total_cost += quantity * unit_cost

        return total_cost

    async def create(self, recipe_data: Dict[str, Any]) -> str:
        """
        Create a new recipe

        Args:
            recipe_data: Recipe document with menu_item_id and ingredients array

        Returns:
            Inserted document ID
        """
        collection = await self._get_collection()

        recipe_data["created_at"] = now_ist()
        recipe_data["updated_at"] = now_ist()

        result = await collection.insert_one(recipe_data)
        return str(result.inserted_id)

    async def _resolve_object_id(self, menu_item_id: str) -> Optional[str]:
        """Resolve human-readable menu item code to its ObjectId string."""
        menu_item = await self.db["menu_items"].find_one({"menu_item_id": menu_item_id})
        return str(menu_item["_id"]) if menu_item else None

    async def update(self, menu_item_id: str, recipe_data: Dict[str, Any]) -> bool:
        collection = await self._get_collection()
        recipe_data["updated_at"] = now_ist()

        result = await collection.update_one({"menu_item_id": menu_item_id}, {"$set": recipe_data})
        if result.modified_count == 0:
            oid = await self._resolve_object_id(menu_item_id)
            if oid:
                result = await collection.update_one({"menu_item_id": oid}, {"$set": recipe_data})

        return result.modified_count > 0

    async def delete(self, menu_item_id: str) -> bool:
        collection = await self._get_collection()
        result = await collection.delete_one({"menu_item_id": menu_item_id})
        if result.deleted_count == 0:
            oid = await self._resolve_object_id(menu_item_id)
            if oid:
                result = await collection.delete_one({"menu_item_id": oid})

        return result.deleted_count > 0


# Singleton instance
_recipe_repository = None


def get_recipe_repository() -> RecipeRepository:
    """Get singleton recipe repository instance"""
    global _recipe_repository
    if _recipe_repository is None:
        _recipe_repository = RecipeRepository()
    return _recipe_repository

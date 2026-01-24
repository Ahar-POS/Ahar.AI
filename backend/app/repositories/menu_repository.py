"""
Menu repository for database operations.

Handles all menu item-related database queries.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.menu_item import MenuItemCreate, MenuItemInDB, MenuItemUpdate, PrepType

logger = logging.getLogger(__name__)


class MenuRepository:
    """Repository for menu item database operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize menu repository.
        
        Args:
            db: MongoDB database instance.
        """
        self.db = db
        self.collection = db.menu_items

    async def create(self, menu_item: MenuItemCreate) -> MenuItemInDB:
        """
        Create a new menu item in the database.
        
        Args:
            menu_item: Menu item creation data.
            
        Returns:
            MenuItemInDB: Created menu item with database ID.
        """
        now = datetime.now(timezone.utc)
        
        menu_item_doc = {
            "name": menu_item.name,
            "description": menu_item.description,
            "price": menu_item.price,
            "category": menu_item.category,
            "tags": [tag.value for tag in menu_item.tags],
            "prep_type": menu_item.prep_type.value,
            "is_available": menu_item.is_available,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        
        result = await self.collection.insert_one(menu_item_doc)
        menu_item_doc["_id"] = str(result.inserted_id)
        
        return MenuItemInDB(**menu_item_doc)

    async def get_by_id(self, item_id: str) -> Optional[MenuItemInDB]:
        """
        Get menu item by ID.
        
        Args:
            item_id: Menu item's database ID.
            
        Returns:
            MenuItemInDB or None if not found.
        """
        try:
            doc = await self.collection.find_one({"_id": ObjectId(item_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
                return MenuItemInDB(**doc)
            return None
        except (ValueError, InvalidId) as e:
            logger.warning(f"Invalid item_id format: {item_id}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_by_id for item_id {item_id}: {e}", exc_info=True)
            return None

    async def get_all(
        self, 
        include_inactive: bool = False,
        category: Optional[str] = None
    ) -> List[MenuItemInDB]:
        """
        Get all menu items.
        
        Args:
            include_inactive: Whether to include soft-deleted items.
            category: Optional category filter.
            
        Returns:
            List of menu items.
        """
        query = {}
        if not include_inactive:
            query["is_active"] = True
        
        if category:
            query["category"] = category
        
        cursor = self.collection.find(query).sort("category", 1).sort("name", 1)
        items = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            items.append(MenuItemInDB(**doc))
        
        return items

    async def get_by_category(self, category: str) -> List[MenuItemInDB]:
        """
        Get all menu items in a specific category.
        
        Args:
            category: Category name to filter by.
            
        Returns:
            List of menu items in the category.
        """
        cursor = self.collection.find({
            "category": category,
            "is_active": True
        }).sort("name", 1)
        
        items = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            items.append(MenuItemInDB(**doc))
        
        return items

    async def get_by_prep_type(self, prep_type: PrepType) -> List[MenuItemInDB]:
        """
        Get all menu items with a specific prep type.
        
        Args:
            prep_type: Preparation type to filter by.
            
        Returns:
            List of menu items with the specified prep type.
        """
        cursor = self.collection.find({
            "prep_type": prep_type.value,
            "is_active": True
        }).sort("name", 1)
        
        items = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            items.append(MenuItemInDB(**doc))
        
        return items

    async def update(self, item_id: str, update_data: MenuItemUpdate) -> Optional[MenuItemInDB]:
        """
        Update menu item details.
        
        Args:
            item_id: Menu item's database ID.
            update_data: Fields to update.
            
        Returns:
            MenuItemInDB or None if not found.
        """
        update_dict = update_data.model_dump(exclude_unset=True)
        
        if not update_dict:
            return await self.get_by_id(item_id)
        
        # Convert enum to value if present
        if "prep_type" in update_dict and update_dict["prep_type"]:
            update_dict["prep_type"] = update_dict["prep_type"].value
        
        # Convert tags list to values if present
        if "tags" in update_dict and update_dict["tags"]:
            update_dict["tags"] = [tag.value for tag in update_dict["tags"]]
        
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(item_id)},
                {"$set": update_dict}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                return await self.get_by_id(item_id)
            return None
        except (ValueError, InvalidId) as e:
            logger.warning(f"Invalid item_id format in update: {item_id}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in update for item_id {item_id}: {e}", exc_info=True)
            return None

    async def soft_delete(self, item_id: str) -> bool:
        """
        Soft delete a menu item (mark as inactive).
        
        Args:
            item_id: Menu item's database ID.
            
        Returns:
            bool: True if successful.
        """
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(item_id)},
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except (ValueError, InvalidId) as e:
            logger.warning(f"Invalid item_id format in soft_delete: {item_id}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error in soft_delete for item_id {item_id}: {e}", exc_info=True)
            return False

    async def get_categories(self) -> List[str]:
        """
        Get all unique categories from menu items.
        
        Returns:
            List of unique category names.
        """
        categories = await self.collection.distinct("category", {"is_active": True})
        return sorted(categories)

    async def ensure_indexes(self) -> None:
        """Create database indexes for the menu_items collection."""
        await self.collection.create_index("category")
        await self.collection.create_index("prep_type")
        await self.collection.create_index("is_active")
        await self.collection.create_index("is_available")

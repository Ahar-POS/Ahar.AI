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

from app.models.menu_item import (
    IngredientTag,
    MenuItemCreate,
    MenuItemInDB,
    MenuItemUpdate,
    PrepType,
)

logger = logging.getLogger(__name__)


def _normalize_doc_to_menu_item(doc: dict) -> MenuItemInDB:
    """
    Normalize a MongoDB document to MenuItemInDB, coercing types for imported/legacy data.
    Handles price as float/string, tags as strings, prep_type as string, missing datetimes.
    """
    doc = dict(doc)
    doc["_id"] = str(doc.get("_id", ""))

    # String fields: coerce from CSV/import (e.g. numeric or non-string)
    doc["name"] = (str(doc.get("name") or "").strip() or "(unknown)")[:100]
    doc["description"] = (str(doc.get("description") or "").strip() or "—")[:500]
    doc["category"] = (str(doc.get("category") or "").strip() or "Uncategorized")[:50]

    # Price: store as int (paise); coerce from float or string; support price, price_inr, or price_amount
    raw_price = doc.get("price")
    if raw_price is None:
        raw_price = doc.get("price_inr")
    if raw_price is None:
        raw_price = doc.get("price_amount")
    if raw_price is None:
        raw_price = 0
    if isinstance(raw_price, float):
        doc["price"] = int(round(raw_price))
    elif isinstance(raw_price, str):
        try:
            doc["price"] = int(round(float(raw_price)))
        except (ValueError, TypeError):
            doc["price"] = 0
    else:
        doc["price"] = int(raw_price) if raw_price is not None else 0
    if doc["price"] < 0:
        doc["price"] = 0

    # Tags: must be list of IngredientTag; DB may have list of strings
    raw_tags = doc.get("tags") or []
    if not isinstance(raw_tags, list):
        raw_tags = [raw_tags] if raw_tags else []
    tags_out = []
    for t in raw_tags:
        if isinstance(t, IngredientTag):
            tags_out.append(t)
        elif isinstance(t, str) and t:
            try:
                tags_out.append(IngredientTag(t))
            except ValueError:
                pass
    doc["tags"] = tags_out

    # Prep type: DB may have string
    raw_prep = doc.get("prep_type")
    if isinstance(raw_prep, PrepType):
        doc["prep_type"] = raw_prep.value
    elif isinstance(raw_prep, str) and raw_prep:
        try:
            doc["prep_type"] = PrepType(raw_prep).value
        except ValueError:
            doc["prep_type"] = PrepType.COLD.value
    else:
        doc["prep_type"] = PrepType.COLD.value

    # Booleans with defaults
    doc.setdefault("is_available", True)
    doc.setdefault("is_active", True)
    if isinstance(doc.get("is_available"), str):
        doc["is_available"] = doc["is_available"].lower() in ("true", "1", "yes")
    if isinstance(doc.get("is_active"), str):
        doc["is_active"] = doc["is_active"].lower() in ("true", "1", "yes")

    # Datetimes: BSON datetime or string from CSV
    now = datetime.now(timezone.utc)
    for key in ("created_at", "updated_at"):
        val = doc.get(key)
        if val is None:
            doc[key] = now
        elif isinstance(val, datetime):
            if val.tzinfo is None:
                doc[key] = val.replace(tzinfo=timezone.utc)
            else:
                doc[key] = val
        elif isinstance(val, str):
            try:
                # Support ISO format (e.g. from CSV or BSON)
                val_clean = val.replace("Z", "+00:00").strip()
                parsed = datetime.fromisoformat(val_clean)
                doc[key] = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except Exception:
                doc[key] = now
        else:
            doc[key] = now

    return MenuItemInDB(**doc)


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
                return _normalize_doc_to_menu_item(doc)
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
            # Include items that are active or that have no is_active field (legacy/imported data)
            query["$or"] = [
                {"is_active": True},
                {"is_active": {"$exists": False}},
            ]
        if category:
            query["category"] = category
        
        cursor = self.collection.find(query).sort("category", 1).sort("name", 1)
        items = []
        async for doc in cursor:
            items.append(_normalize_doc_to_menu_item(doc))
        return items

    async def get_by_category(self, category: str) -> List[MenuItemInDB]:
        """
        Get all menu items in a specific category.
        
        Args:
            category: Category name to filter by.
            
        Returns:
            List of menu items in the category.
        """
        filter_query = {
            "category": category,
            "$or": [
                {"is_active": True},
                {"is_active": {"$exists": False}},
            ],
        }
        cursor = self.collection.find(filter_query).sort("name", 1)
        items = []
        async for doc in cursor:
            items.append(_normalize_doc_to_menu_item(doc))
        return items

    async def get_by_prep_type(self, prep_type: PrepType) -> List[MenuItemInDB]:
        """
        Get all menu items with a specific prep type.
        
        Args:
            prep_type: Preparation type to filter by.
            
        Returns:
            List of menu items with the specified prep type.
        """
        filter_query = {
            "prep_type": prep_type.value,
            "$or": [
                {"is_active": True},
                {"is_active": {"$exists": False}},
            ],
        }
        cursor = self.collection.find(filter_query).sort("name", 1)
        items = []
        async for doc in cursor:
            items.append(_normalize_doc_to_menu_item(doc))
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
        filter_query = {
            "$or": [
                {"is_active": True},
                {"is_active": {"$exists": False}},
            ]
        }
        categories = await self.collection.distinct("category", filter_query)
        return sorted(categories)

    async def ensure_indexes(self) -> None:
        """Create database indexes for the menu_items collection."""
        await self.collection.create_index("category")
        await self.collection.create_index("prep_type")
        await self.collection.create_index("is_active")
        await self.collection.create_index("is_available")

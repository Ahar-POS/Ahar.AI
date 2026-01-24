"""
Table repository for database operations.

Handles all table-related database queries.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.table import TableCreate, TableInDB, TableStatus, TableUpdate

logger = logging.getLogger(__name__)


class TableRepository:
    """Repository for table database operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize table repository.
        
        Args:
            db: MongoDB database instance.
        """
        self.db = db
        self.collection = db.tables

    async def create(self, table: TableCreate) -> TableInDB:
        """
        Create a new table in the database.
        
        Args:
            table: Table creation data.
            
        Returns:
            TableInDB: Created table with database ID.
        """
        now = datetime.now(timezone.utc)
        
        table_doc = {
            "table_number": table.table_number,
            "location": table.location,
            "capacity": table.capacity,
            "status": table.status.value,
            "restaurant_id": table.restaurant_id,
            "created_by_user_id": table.created_by_user_id,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        
        result = await self.collection.insert_one(table_doc)
        table_doc["_id"] = str(result.inserted_id)
        
        return TableInDB(**table_doc)

    async def get_by_id(self, table_id: str) -> Optional[TableInDB]:
        """
        Get table by ID.
        
        Args:
            table_id: Table's database ID.
            
        Returns:
            TableInDB or None if not found.
        """
        try:
            doc = await self.collection.find_one({"_id": ObjectId(table_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
                return TableInDB(**doc)
            return None
        except (ValueError, InvalidId) as e:
            logger.warning(f"Invalid table_id format: {table_id}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_by_id for table_id {table_id}: {e}", exc_info=True)
            return None

    async def get_by_restaurant(
        self, 
        restaurant_id: str, 
        include_inactive: bool = False
    ) -> List[TableInDB]:
        """
        Get all tables for a restaurant.
        
        Args:
            restaurant_id: Restaurant identifier.
            include_inactive: Whether to include soft-deleted tables.
            
        Returns:
            List of tables.
        """
        query = {"restaurant_id": restaurant_id}
        if not include_inactive:
            query["is_active"] = True
        
        cursor = self.collection.find(query).sort("table_number", 1)
        tables = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            tables.append(TableInDB(**doc))
        
        return tables

    async def get_by_table_number(
        self, 
        restaurant_id: str, 
        table_number: int
    ) -> Optional[TableInDB]:
        """
        Get table by table number within a restaurant.
        
        Args:
            restaurant_id: Restaurant identifier.
            table_number: Table number.
            
        Returns:
            TableInDB or None if not found.
        """
        doc = await self.collection.find_one({
            "restaurant_id": restaurant_id,
            "table_number": table_number,
            "is_active": True
        })
        
        if doc:
            doc["_id"] = str(doc["_id"])
            return TableInDB(**doc)
        return None

    async def get_by_status(
        self, 
        restaurant_id: str, 
        status: TableStatus
    ) -> List[TableInDB]:
        """
        Get all tables with a specific status.
        
        Args:
            restaurant_id: Restaurant identifier.
            status: Table status to filter by.
            
        Returns:
            List of tables with the specified status.
        """
        cursor = self.collection.find({
            "restaurant_id": restaurant_id,
            "status": status.value,
            "is_active": True
        }).sort("table_number", 1)
        
        tables = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            tables.append(TableInDB(**doc))
        
        return tables

    async def update(self, table_id: str, update_data: TableUpdate) -> Optional[TableInDB]:
        """
        Update table details.
        
        Args:
            table_id: Table's database ID.
            update_data: Fields to update.
            
        Returns:
            TableInDB or None if not found.
        """
        update_dict = update_data.model_dump(exclude_unset=True)
        
        if not update_dict:
            return await self.get_by_id(table_id)
        
        # Convert enum to value if present
        if "status" in update_dict and update_dict["status"]:
            update_dict["status"] = update_dict["status"].value
        
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(table_id)},
                {"$set": update_dict}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                return await self.get_by_id(table_id)
            return None
        except (ValueError, InvalidId) as e:
            logger.warning(f"Invalid table_id format in update: {table_id}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in update for table_id {table_id}: {e}", exc_info=True)
            return None

    async def update_status(self, table_id: str, status: TableStatus) -> Optional[TableInDB]:
        """
        Update table status.
        
        Args:
            table_id: Table's database ID.
            status: New status value.
            
        Returns:
            TableInDB or None if not found.
        """
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(table_id)},
                {
                    "$set": {
                        "status": status.value,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                return await self.get_by_id(table_id)
            return None
        except (ValueError, InvalidId) as e:
            logger.warning(f"Invalid table_id format in update_status: {table_id}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error in update_status for table_id {table_id}: {e}", exc_info=True)
            return None

    async def soft_delete(self, table_id: str) -> bool:
        """
        Soft delete a table (mark as inactive).
        
        Args:
            table_id: Table's database ID.
            
        Returns:
            bool: True if successful.
        """
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(table_id)},
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except (ValueError, InvalidId) as e:
            logger.warning(f"Invalid table_id format in soft_delete: {table_id}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error in soft_delete for table_id {table_id}: {e}", exc_info=True)
            return False

    async def table_number_exists(
        self, 
        restaurant_id: str, 
        table_number: int,
        exclude_table_id: Optional[str] = None
    ) -> bool:
        """
        Check if table number already exists in restaurant.
        
        Args:
            restaurant_id: Restaurant identifier.
            table_number: Table number to check.
            exclude_table_id: Optional table ID to exclude from check (for updates).
            
        Returns:
            bool: True if table number exists.
        """
        query = {
            "restaurant_id": restaurant_id,
            "table_number": table_number,
            "is_active": True
        }
        
        if exclude_table_id:
            try:
                query["_id"] = {"$ne": ObjectId(exclude_table_id)}
            except (ValueError, InvalidId) as e:
                logger.warning(f"Invalid exclude_table_id format: {exclude_table_id}", exc_info=True)
        
        count = await self.collection.count_documents(query)
        return count > 0

    async def ensure_indexes(self) -> None:
        """Create database indexes for the tables collection."""
        # Unique constraint on table_number per restaurant (for active tables)
        await self.collection.create_index(
            [("restaurant_id", 1), ("table_number", 1), ("is_active", 1)],
            unique=True,
            partialFilterExpression={"is_active": True}
        )
        await self.collection.create_index("restaurant_id")
        await self.collection.create_index("status")
        await self.collection.create_index("is_active")

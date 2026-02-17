"""
User repository for database operations.

Handles all user-related database queries.
"""

from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.user import UserCreate, UserInDB, UserRole, UserStatus, UserUpdate


class UserRepository:
    """Repository for user database operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize user repository.
        
        Args:
            db: MongoDB database instance.
        """
        self.db = db
        self.collection = db.users

    async def create(self, user: UserCreate, password_hash: str) -> UserInDB:
        """
        Create a new user in the database.
        
        Args:
            user: User creation data.
            password_hash: Hashed password.
            
        Returns:
            UserInDB: Created user with database ID.
        """
        now = datetime.now(timezone.utc)
        
        user_doc = {
            "email": user.email.lower(),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value,
            "status": user.status.value,
            "restaurant_id": user.restaurant_id,
            "password_hash": password_hash,
            "created_at": now,
            "updated_at": now,
        }
        
        result = await self.collection.insert_one(user_doc)
        user_doc["_id"] = str(result.inserted_id)
        
        return UserInDB(**user_doc)

    async def get_by_id(self, user_id: str) -> Optional[UserInDB]:
        """
        Get user by ID.
        
        Args:
            user_id: User's database ID.
            
        Returns:
            UserInDB or None if not found.
        """
        try:
            doc = await self.collection.find_one({"_id": ObjectId(user_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
                return UserInDB(**doc)
            return None
        except Exception:
            return None

    async def get_by_email(self, email: str) -> Optional[UserInDB]:
        """
        Get user by email address.
        
        Args:
            email: User's email address.
            
        Returns:
            UserInDB or None if not found.
        """
        doc = await self.collection.find_one({"email": email.lower()})
        if doc:
            doc["_id"] = str(doc["_id"])
            return UserInDB(**doc)
        return None

    async def update(self, user_id: str, update_data: UserUpdate) -> Optional[UserInDB]:
        """
        Update user details.
        
        Args:
            user_id: User's database ID.
            update_data: Fields to update.
            
        Returns:
            UserInDB or None if not found.
        """
        update_dict = update_data.model_dump(exclude_unset=True)
        
        if not update_dict:
            return await self.get_by_id(user_id)
        
        # Convert enum to value if present
        if "status" in update_dict and update_dict["status"]:
            update_dict["status"] = update_dict["status"].value
        
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_dict}
        )
        
        if result.modified_count > 0 or result.matched_count > 0:
            return await self.get_by_id(user_id)
        return None

    async def update_status(self, user_id: str, status: UserStatus) -> Optional[UserInDB]:
        """
        Update user account status.
        
        Args:
            user_id: User's database ID.
            status: New status value.
            
        Returns:
            UserInDB or None if not found.
        """
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "status": status.value,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count > 0 or result.matched_count > 0:
            return await self.get_by_id(user_id)
        return None

    async def email_exists(self, email: str) -> bool:
        """
        Check if email is already registered.

        Args:
            email: Email address to check.

        Returns:
            bool: True if email exists.
        """
        count = await self.collection.count_documents({"email": email.lower()})
        return count > 0

    async def list_by_restaurant_and_role(
        self, restaurant_id: str, role: UserRole
    ) -> List[UserInDB]:
        """
        List users for a restaurant with the given role.

        Args:
            restaurant_id: Restaurant identifier.
            role: User role to filter by.

        Returns:
            List of users, ordered by created_at ascending.
        """
        cursor = self.collection.find(
            {"restaurant_id": restaurant_id, "role": role.value}
        ).sort("created_at", 1)
        users = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            users.append(UserInDB(**doc))
        return users

    async def delete(self, user_id: str) -> bool:
        """
        Permanently delete a user by ID.

        Args:
            user_id: User's database ID.

        Returns:
            bool: True if a user was deleted.
        """
        try:
            result = await self.collection.delete_one({"_id": ObjectId(user_id)})
            return result.deleted_count > 0
        except Exception:
            return False

    async def ensure_indexes(self) -> None:
        """Create database indexes for the users collection."""
        await self.collection.create_index("email", unique=True)
        await self.collection.create_index("status")
        await self.collection.create_index("role")
        await self.collection.create_index("restaurant_id")

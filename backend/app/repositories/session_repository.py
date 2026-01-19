"""
Session repository for database operations.

Handles all session-related database queries for server-side session management.
"""

from datetime import datetime, timezone
from typing import Optional, List

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.session import SessionCreate, SessionInDB


class SessionRepository:
    """Repository for session database operations."""

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize session repository.
        
        Args:
            db: MongoDB database instance.
        """
        self.db = db
        self.collection = db.sessions

    async def create(self, session: SessionCreate) -> SessionInDB:
        """
        Create a new session in the database.
        
        Args:
            session: Session creation data.
            
        Returns:
            SessionInDB: Created session with database ID.
        """
        now = datetime.now(timezone.utc)
        
        session_doc = {
            "user_id": session.user_id,
            "token": session.token,
            "expires_at": session.expires_at,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "created_at": now,
        }
        
        result = await self.collection.insert_one(session_doc)
        session_doc["_id"] = str(result.inserted_id)
        
        return SessionInDB(**session_doc)

    async def get_by_token(self, token: str) -> Optional[SessionInDB]:
        """
        Get session by token.
        
        Args:
            token: Session token.
            
        Returns:
            SessionInDB or None if not found.
        """
        doc = await self.collection.find_one({"token": token})
        if doc:
            doc["_id"] = str(doc["_id"])
            return SessionInDB(**doc)
        return None

    async def get_valid_session(self, token: str) -> Optional[SessionInDB]:
        """
        Get session by token if it hasn't expired.
        
        Args:
            token: Session token.
            
        Returns:
            SessionInDB or None if not found or expired.
        """
        now = datetime.now(timezone.utc)
        doc = await self.collection.find_one({
            "token": token,
            "expires_at": {"$gt": now}
        })
        if doc:
            doc["_id"] = str(doc["_id"])
            return SessionInDB(**doc)
        return None

    async def delete_by_token(self, token: str) -> bool:
        """
        Delete session by token.
        
        Args:
            token: Session token to delete.
            
        Returns:
            bool: True if session was deleted.
        """
        result = await self.collection.delete_one({"token": token})
        return result.deleted_count > 0

    async def delete_user_sessions(self, user_id: str) -> int:
        """
        Delete all sessions for a user.
        
        Args:
            user_id: User's database ID.
            
        Returns:
            int: Number of sessions deleted.
        """
        result = await self.collection.delete_many({"user_id": user_id})
        return result.deleted_count

    async def delete_other_sessions(self, user_id: str, current_token: str) -> int:
        """
        Delete all sessions for a user except the current one.
        
        Args:
            user_id: User's database ID.
            current_token: Token of current session to keep.
            
        Returns:
            int: Number of sessions deleted.
        """
        result = await self.collection.delete_many({
            "user_id": user_id,
            "token": {"$ne": current_token}
        })
        return result.deleted_count

    async def get_user_sessions(self, user_id: str) -> List[SessionInDB]:
        """
        Get all active sessions for a user.
        
        Args:
            user_id: User's database ID.
            
        Returns:
            List[SessionInDB]: List of user's sessions.
        """
        now = datetime.now(timezone.utc)
        cursor = self.collection.find({
            "user_id": user_id,
            "expires_at": {"$gt": now}
        })
        
        sessions = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            sessions.append(SessionInDB(**doc))
        
        return sessions

    async def cleanup_expired(self) -> int:
        """
        Remove all expired sessions.
        
        Returns:
            int: Number of sessions removed.
        """
        now = datetime.now(timezone.utc)
        result = await self.collection.delete_many({"expires_at": {"$lt": now}})
        return result.deleted_count

    async def ensure_indexes(self) -> None:
        """Create database indexes for the sessions collection."""
        await self.collection.create_index("token", unique=True)
        await self.collection.create_index("user_id")
        # TTL index for automatic expiration
        await self.collection.create_index("expires_at", expireAfterSeconds=0)

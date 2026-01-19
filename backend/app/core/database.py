"""
MongoDB database connection management.

Provides async MongoDB client using Motor driver.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional

from app.core.config import get_settings


class Database:
    """MongoDB database connection manager."""

    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None


db = Database()


async def connect_to_database() -> None:
    """
    Initialize MongoDB connection.
    
    Called during application startup.
    """
    settings = get_settings()
    db.client = AsyncIOMotorClient(settings.MONGODB_URI)
    db.db = db.client[settings.DB_NAME]
    
    # Verify connection
    await db.client.admin.command("ping")
    print(f"Connected to MongoDB: {settings.DB_NAME}")


async def close_database_connection() -> None:
    """
    Close MongoDB connection.
    
    Called during application shutdown.
    """
    if db.client:
        db.client.close()
        print("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """
    Get database instance for dependency injection.
    
    Returns:
        AsyncIOMotorDatabase: MongoDB database instance.
    
    Raises:
        RuntimeError: If database is not connected.
    """
    if db.db is None:
        raise RuntimeError("Database not connected. Call connect_to_database() first.")
    return db.db

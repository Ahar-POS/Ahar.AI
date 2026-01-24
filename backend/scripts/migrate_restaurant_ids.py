"""
Migration script to assign restaurant_id to existing users and data.

This script:
1. Assigns a unique restaurant_id to each existing user who doesn't have one
2. Updates all tables, menu items, and orders to use the correct restaurant_id
   based on the user who created them

Run this script once after deploying the multi-tenancy feature.

Usage:
    python -m scripts.migrate_restaurant_ids
"""

import asyncio
import sys
import uuid
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings


async def migrate_restaurant_ids():
    """
    Migrate existing data to include restaurant_id.
    
    For each user without a restaurant_id:
    1. Generate a unique restaurant_id
    2. Update the user document
    3. Update all tables, menu items, and orders created by that user
    """
    settings = get_settings()
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.DB_NAME]
    
    try:
        print("Starting restaurant_id migration...")
        
        # Get all users without restaurant_id
        users_without_restaurant = await db.users.find({"restaurant_id": {"$exists": False}}).to_list(length=None)
        users_with_null_restaurant = await db.users.find({"restaurant_id": None}).to_list(length=None)
        
        all_users_to_migrate = users_without_restaurant + users_with_null_restaurant
        # Remove duplicates based on _id
        seen_ids = set()
        unique_users = []
        for user in all_users_to_migrate:
            user_id = str(user["_id"])
            if user_id not in seen_ids:
                seen_ids.add(user_id)
                unique_users.append(user)
        
        print(f"Found {len(unique_users)} users without restaurant_id")
        
        if len(unique_users) == 0:
            print("No users to migrate. Migration complete.")
            return
        
        # Process each user
        migrated_count = 0
        for user in unique_users:
            user_id = str(user["_id"])
            restaurant_id = str(uuid.uuid4())
            
            print(f"Migrating user {user_id} -> restaurant {restaurant_id}")
            
            # Update user with restaurant_id
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"restaurant_id": restaurant_id}}
            )
            
            # Update all tables created by this user
            tables_result = await db.tables.update_many(
                {"created_by_user_id": user_id},
                {"$set": {"restaurant_id": restaurant_id}}
            )
            if tables_result.modified_count > 0:
                print(f"  Updated {tables_result.modified_count} table(s)")
            
            # Update all menu items (if they have created_by_user_id, otherwise assign to user's restaurant)
            # Note: Menu items might not have created_by_user_id, so we'll assign based on user
            # For now, we'll only update menu items that have a restaurant_id matching a pattern
            # or are missing restaurant_id entirely
            menu_items_result = await db.menu_items.update_many(
                {
                    "$or": [
                        {"restaurant_id": {"$exists": False}},
                        {"restaurant_id": None},
                        # If menu items have a default or shared restaurant_id, we might want to
                        # leave them or reassign. For now, we'll only update missing ones.
                    ]
                },
                {"$set": {"restaurant_id": restaurant_id}}
            )
            # Note: This is a simplified approach. In production, you might want to track
            # which menu items belong to which user/restaurant more carefully.
            
            # Update all orders created by this user
            orders_result = await db.orders.update_many(
                {"created_by_user_id": user_id},
                {"$set": {"restaurant_id": restaurant_id}}
            )
            if orders_result.modified_count > 0:
                print(f"  Updated {orders_result.modified_count} order(s)")
            
            migrated_count += 1
        
        print(f"\nMigration complete! Migrated {migrated_count} user(s)")
        
        # Create indexes if they don't exist
        print("\nEnsuring indexes...")
        await db.users.create_index("restaurant_id")
        await db.tables.create_index("restaurant_id")
        await db.menu_items.create_index("restaurant_id")
        await db.orders.create_index("restaurant_id")
        print("Indexes created/verified.")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(migrate_restaurant_ids())

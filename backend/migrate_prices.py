"""
Price Migration Script

Consolidates price fields in menu_items collection:
- Migrates price_inr → price (when price is None or 0)
- Removes price_inr and price_amount fields after migration
- Shows before/after comparison for verification

Usage:
    python migrate_prices.py --dry-run  # Preview changes without applying
    python migrate_prices.py            # Apply changes to database
"""

import asyncio
import argparse
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone


class PriceMigrator:
    """Handles migration of menu item prices to standardized format."""

    def __init__(self, mongodb_uri: str = "mongodb://localhost:27017", db_name: str = "ahar_pos"):
        """
        Initialize migrator.

        Args:
            mongodb_uri: MongoDB connection string
            db_name: Database name
        """
        self.mongodb_uri = mongodb_uri
        self.db_name = db_name
        self.client = None
        self.db = None

    async def connect(self):
        """Connect to MongoDB."""
        self.client = AsyncIOMotorClient(self.mongodb_uri)
        self.db = self.client[self.db_name]
        print(f"✓ Connected to MongoDB: {self.db_name}")

    async def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            print("✓ Disconnected from MongoDB")

    async def analyze_prices(self):
        """
        Analyze current price field state.

        Returns:
            Dictionary with analysis results
        """
        collection = self.db.menu_items

        # Count total items
        total = await collection.count_documents({})

        # Items with price field
        has_price = await collection.count_documents({"price": {"$exists": True, "$ne": None}})

        # Items with price_inr field
        has_price_inr = await collection.count_documents({"price_inr": {"$exists": True, "$ne": None}})

        # Items with price_amount field
        has_price_amount = await collection.count_documents({"price_amount": {"$exists": True, "$ne": None}})

        # Items with no valid price
        no_price = await collection.count_documents({
            "$or": [
                {"price": {"$exists": False}},
                {"price": None},
                {"price": 0}
            ],
            "$or": [
                {"price_inr": {"$exists": False}},
                {"price_inr": None},
                {"price_inr": 0}
            ]
        })

        return {
            "total": total,
            "has_price": has_price,
            "has_price_inr": has_price_inr,
            "has_price_amount": has_price_amount,
            "no_price": no_price
        }

    async def get_items_to_migrate(self):
        """
        Get all items that need price migration.

        Returns:
            List of documents that will be updated
        """
        collection = self.db.menu_items

        # Find items where price is None/0 but price_inr exists
        cursor = collection.find({
            "$or": [
                {"price": {"$exists": False}},
                {"price": None},
                {"price": 0}
            ],
            "price_inr": {"$exists": True, "$ne": None, "$ne": 0}
        })

        items = await cursor.to_list(length=None)
        return items

    async def get_conflicting_items(self):
        """
        Get items where both price and price_inr exist with different values.

        Returns:
            List of documents with conflicting prices
        """
        collection = self.db.menu_items

        # Find items with both fields
        cursor = collection.find({
            "price": {"$exists": True, "$ne": None, "$ne": 0},
            "price_inr": {"$exists": True, "$ne": None, "$ne": 0}
        })

        items = await cursor.to_list(length=None)

        # Filter to only those where values differ
        conflicting = []
        for item in items:
            if item.get("price") != item.get("price_inr"):
                conflicting.append(item)

        return conflicting

    async def migrate_prices(self, dry_run: bool = True):
        """
        Migrate prices to standardized format.

        Args:
            dry_run: If True, only show what would be changed

        Returns:
            Number of items updated
        """
        collection = self.db.menu_items

        # Get items to migrate
        items_to_migrate = await self.get_items_to_migrate()
        conflicting_items = await self.get_conflicting_items()

        print(f"\n{'=' * 80}")
        print(f"MIGRATION PLAN")
        print(f"{'=' * 80}")

        if items_to_migrate:
            print(f"\n📝 {len(items_to_migrate)} items will be updated (price_inr → price):")
            print(f"{'─' * 80}")
            for item in items_to_migrate:
                print(f"  • {item.get('name', 'Unknown')}")
                print(f"    Current:  price={item.get('price')}  price_inr={item.get('price_inr')}")
                print(f"    New:      price={item.get('price_inr')}  (₹{item.get('price_inr', 0) / 100:.2f})")
        else:
            print("\n✓ No items need price migration")

        if conflicting_items:
            print(f"\n⚠️  {len(conflicting_items)} items have CONFLICTING prices:")
            print(f"{'─' * 80}")
            for item in conflicting_items:
                print(f"  • {item.get('name', 'Unknown')}")
                print(f"    price:     {item.get('price')} (₹{item.get('price', 0) / 100:.2f})")
                print(f"    price_inr: {item.get('price_inr')} (₹{item.get('price_inr', 0) / 100:.2f})")
                print(f"    → Will keep 'price' value (₹{item.get('price', 0) / 100:.2f})")

        # Get all items with legacy fields to clean up
        items_with_price_inr = await collection.count_documents({"price_inr": {"$exists": True}})
        items_with_price_amount = await collection.count_documents({"price_amount": {"$exists": True}})

        if items_with_price_inr or items_with_price_amount:
            print(f"\n🧹 Cleanup:")
            if items_with_price_inr:
                print(f"  • Remove 'price_inr' field from {items_with_price_inr} items")
            if items_with_price_amount:
                print(f"  • Remove 'price_amount' field from {items_with_price_amount} items")

        print(f"\n{'=' * 80}")

        if dry_run:
            print("\n🔍 DRY RUN - No changes will be made")
            print("Run without --dry-run to apply changes")
            return 0

        # Apply migration
        updated_count = 0
        now = datetime.now(timezone.utc)

        # Update items that need price migration
        for item in items_to_migrate:
            result = await collection.update_one(
                {"_id": item["_id"]},
                {
                    "$set": {
                        "price": item.get("price_inr"),
                        "updated_at": now
                    }
                }
            )
            if result.modified_count > 0:
                updated_count += 1

        # Clean up legacy fields from ALL items
        cleanup_result = await collection.update_many(
            {},
            {
                "$unset": {
                    "price_inr": "",
                    "price_amount": ""
                },
                "$set": {
                    "updated_at": now
                }
            }
        )

        print(f"\n✅ Migration complete!")
        print(f"  • Updated {updated_count} item prices")
        print(f"  • Cleaned up legacy fields from {cleanup_result.modified_count} items")

        return updated_count

    async def verify_migration(self):
        """Verify migration was successful."""
        collection = self.db.menu_items

        # Check for any remaining issues
        items_with_zero_price = await collection.count_documents({
            "$or": [
                {"price": {"$exists": False}},
                {"price": None},
                {"price": 0}
            ]
        })

        items_with_price_inr = await collection.count_documents({"price_inr": {"$exists": True}})
        items_with_price_amount = await collection.count_documents({"price_amount": {"$exists": True}})

        print(f"\n{'=' * 80}")
        print(f"VERIFICATION")
        print(f"{'=' * 80}")

        if items_with_zero_price == 0 and items_with_price_inr == 0 and items_with_price_amount == 0:
            print("\n✅ All menu items have valid prices")
            print("✅ All legacy price fields removed")
        else:
            if items_with_zero_price > 0:
                print(f"\n⚠️  {items_with_zero_price} items still have price=0 or None")
            if items_with_price_inr > 0:
                print(f"⚠️  {items_with_price_inr} items still have 'price_inr' field")
            if items_with_price_amount > 0:
                print(f"⚠️  {items_with_price_amount} items still have 'price_amount' field")

        # Show sample of migrated items
        print("\nSample of menu items after migration:")
        print(f"{'─' * 80}")
        cursor = collection.find().limit(5)
        async for item in cursor:
            print(f"  • {item.get('name')}: ₹{item.get('price', 0) / 100:.2f}")


async def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(description="Migrate menu item prices to standardized format")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )
    parser.add_argument(
        "--mongodb-uri",
        default="mongodb://localhost:27017",
        help="MongoDB connection URI"
    )
    parser.add_argument(
        "--db-name",
        default="ahar_pos",
        help="Database name"
    )

    args = parser.parse_args()

    migrator = PriceMigrator(mongodb_uri=args.mongodb_uri, db_name=args.db_name)

    try:
        await migrator.connect()

        # Show current state
        analysis = await migrator.analyze_prices()
        print(f"\nCurrent State:")
        print(f"  Total menu items:        {analysis['total']}")
        print(f"  Items with 'price':      {analysis['has_price']}")
        print(f"  Items with 'price_inr':  {analysis['has_price_inr']}")
        print(f"  Items with 'price_amount': {analysis['has_price_amount']}")
        if analysis['no_price'] > 0:
            print(f"  ⚠️  Items with no price:  {analysis['no_price']}")

        # Run migration
        await migrator.migrate_prices(dry_run=args.dry_run)

        # Verify if not dry run
        if not args.dry_run:
            await migrator.verify_migration()

    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await migrator.close()


if __name__ == "__main__":
    asyncio.run(main())

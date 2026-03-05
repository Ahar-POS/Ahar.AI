"""
Script to approve a shopping list (bypasses authentication)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.shopping_list_service import get_shopping_list_service
from app.core.database import connect_to_database, close_database_connection


async def approve_list():
    """Approve the pending shopping list"""
    await connect_to_database()

    service = get_shopping_list_service()

    # Get pending lists
    lists = await service.get_pending_shopping_lists()

    if not lists:
        print("No pending shopping lists found")
        await close_database_connection()
        return

    # Approve the first pending list
    list_to_approve = lists[0]
    list_id = str(list_to_approve['_id'])

    print(f"\n=== APPROVING SHOPPING LIST ===")
    print(f"List ID: {list_to_approve.get('list_id')}")
    print(f"Total Cost: ₹{list_to_approve.get('total_cost_inr', 0) / 100:.2f}")
    print(f"Items: {len(list_to_approve.get('items', []))}")
    print()

    # Approve it (simulating admin user)
    success = await service.approve_list(
        list_id=list_id,
        user_id="test_admin_user",
        notes="Approved via script - all items needed for operations"
    )

    if success:
        print("✅ Shopping list approved successfully!")
        print(f"MongoDB ID: {list_id}")
    else:
        print("❌ Failed to approve shopping list")

    await close_database_connection()


if __name__ == "__main__":
    asyncio.run(approve_list())

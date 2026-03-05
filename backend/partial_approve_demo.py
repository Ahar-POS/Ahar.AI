"""
Script to demonstrate partial approval of shopping list items
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.shopping_list_service import get_shopping_list_service
from app.core.database import connect_to_database, close_database_connection, get_database
from datetime import datetime


async def demo_partial_approval():
    """Demonstrate partial approval workflow"""
    await connect_to_database()
    db = get_database()

    # Create a new shopping list for partial approval demo
    print("\n=== CREATING NEW SHOPPING LIST FOR PARTIAL APPROVAL DEMO ===\n")

    result = await db.shopping_lists.insert_one({
        "list_id": "SL_2026-02-27_PARTIAL",
        "generated_at": datetime.utcnow(),
        "generated_by": "inventory_agent",
        "status": "pending",
        "urgency_summary": {
            "urgent_count": 2,
            "standard_count": 1,
            "low_priority_count": 1
        },
        "total_cost_inr": 50000,
        "estimated_total": 50000,
        "items": [
            {
                "material_id": "RM020",
                "material_name": "Tomatoes",
                "urgency": "URGENT",
                "quantity_to_order": 5000,
                "unit": "Gram",
                "line_total_inr": 15000,
                "supplier_name": "Veggie Mart",
                "item_status": "pending"
            },
            {
                "material_id": "RM021",
                "material_name": "Onions",
                "urgency": "URGENT",
                "quantity_to_order": 10000,
                "unit": "Gram",
                "line_total_inr": 8000,
                "supplier_name": "Veggie Mart",
                "item_status": "pending"
            },
            {
                "material_id": "RM022",
                "material_name": "Bell Peppers",
                "urgency": "STANDARD",
                "quantity_to_order": 2000,
                "unit": "Gram",
                "line_total_inr": 12000,
                "supplier_name": "Veggie Mart",
                "item_status": "pending"
            },
            {
                "material_id": "RM023",
                "material_name": "Mushrooms",
                "urgency": "LOW_PRIORITY",
                "quantity_to_order": 1000,
                "unit": "Gram",
                "line_total_inr": 15000,
                "supplier_name": "Specialty Foods",
                "item_status": "pending"
            }
        ],
        "confidence_score": 0.85,
        "reasoning": "Mixed urgency items for partial approval demo",
        "reviewed_at": None,
        "reviewed_by": None,
        "approval_notes": None
    })

    list_id = str(result.inserted_id)
    print(f"Created shopping list: SL_2026-02-27_PARTIAL")
    print(f"MongoDB ID: {list_id}")
    print(f"Total items: 4")
    print(f"Total cost: ₹500.00")

    # Approve only URGENT items
    print("\n=== APPROVING ONLY URGENT ITEMS ===\n")

    service = get_shopping_list_service()
    urgent_items = ["RM020", "RM021"]  # Only approve tomatoes and onions

    success = await service.approve_items(
        list_id=list_id,
        material_ids=urgent_items,
        user_id="test_admin_user",
        notes="Approved urgent items only. Will review standard and low priority items later."
    )

    if success:
        print(f"✅ Partially approved {len(urgent_items)} items:")
        print("   - RM020: Tomatoes (URGENT)")
        print("   - RM021: Onions (URGENT)")
        print("\nRemaining items still pending:")
        print("   - RM022: Bell Peppers (STANDARD)")
        print("   - RM023: Mushrooms (LOW_PRIORITY)")
    else:
        print("❌ Partial approval failed")

    # Show updated status
    print("\n=== SHOPPING LIST STATUS ===\n")
    updated_list = await db.shopping_lists.find_one({"_id": result.inserted_id})
    print(f"Status: {updated_list.get('status')}")
    print(f"Reviewed by: {updated_list.get('reviewed_by')}")
    print(f"Notes: {updated_list.get('approval_notes')}")

    print("\nItem statuses:")
    for item in updated_list.get('items', []):
        print(f"  - {item.get('material_name')}: {item.get('item_status')}")

    await close_database_connection()


if __name__ == "__main__":
    asyncio.run(demo_partial_approval())

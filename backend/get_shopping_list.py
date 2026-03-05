"""
Script to get pending shopping lists (bypasses authentication)
"""
import asyncio
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

from app.services.shopping_list_service import get_shopping_list_service
from app.core.database import connect_to_database, close_database_connection


async def get_pending_lists():
    """Get pending shopping lists"""
    await connect_to_database()

    service = get_shopping_list_service()
    lists = await service.get_pending_shopping_lists()

    print("\n=== PENDING SHOPPING LISTS ===\n")

    for lst in lists:
        print(f"List ID: {lst.get('list_id')}")
        print(f"Generated: {lst.get('generated_at')}")
        print(f"Status: {lst.get('status')}")
        print(f"Total Cost: ₹{lst.get('total_cost_inr', 0) / 100:.2f}")
        print(f"Urgency: {lst.get('urgency_summary', {})}")
        print(f"Items: {len(lst.get('items', []))}")
        print(f"MongoDB ID: {lst.get('_id')}")
        print("\nItems:")

        for i, item in enumerate(lst.get('items', [])[:5], 1):  # Show first 5 items
            print(f"  {i}. {item.get('material_name')} ({item.get('material_id')})")
            print(f"     Urgency: {item.get('urgency')} - {item.get('urgency_reason')}")
            print(f"     Quantity: {item.get('quantity_to_order')} {item.get('unit')}")
            print(f"     Cost: ₹{item.get('line_total_inr', 0) / 100:.2f}")
            print(f"     Supplier: {item.get('supplier_name')}")

        if len(lst.get('items', [])) > 5:
            print(f"  ... and {len(lst.get('items', [])) - 5} more items")

        print("\nSupplier Breakdown:")
        for supplier in lst.get('supplier_breakdown', []):
            print(f"  - {supplier.get('supplier_name')}: {supplier.get('item_count')} items, ₹{supplier.get('total_cost_inr', 0) / 100:.2f}")

        print("\n" + "="*60 + "\n")

    await close_database_connection()


if __name__ == "__main__":
    asyncio.run(get_pending_lists())

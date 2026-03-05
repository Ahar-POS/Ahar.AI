"""
Test script to manually trigger inventory agent and see detailed output
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.agents.inventory_agent import get_inventory_agent
from app.core.database import connect_to_database, close_database_connection
from datetime import datetime


async def test_inventory_agent():
    """Test inventory agent execution"""
    print("Connecting to database...")
    await connect_to_database()

    print("Getting inventory agent...")
    agent = get_inventory_agent()

    print("Executing agent...")
    decision = await agent.execute({
        'trigger': 'manual_test',
        'timestamp': datetime.utcnow()
    })

    print("\n=== AGENT DECISION ===")
    print(f"Actions: {len(decision.actions)}")
    print(f"Reasoning: {decision.reasoning}")
    print(f"Confidence: {decision.confidence}")

    if decision.actions:
        for i, action in enumerate(decision.actions):
            print(f"\nAction {i+1}:")
            print(f"  Type: {action.action_type}")
            print(f"  Estimated Cost: ₹{action.estimated_cost/100:.2f}")
            print(f"  Reasoning: {action.reasoning}")
            print(f"  Data: {action.data.keys() if hasattr(action.data, 'keys') else action.data}")

    print("\n=== DONE ===")

    await close_database_connection()


if __name__ == "__main__":
    asyncio.run(test_inventory_agent())

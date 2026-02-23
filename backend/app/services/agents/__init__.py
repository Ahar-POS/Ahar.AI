"""
Autonomous Agents Package

Contains specialized AI agents for restaurant operations:
- BaseAgent: Abstract base class for all agents
- InventoryAgent: Autonomous inventory management
- FinancialAgent: Financial analysis and P&L generation
- KitchenAgent: Kitchen operations optimization (future)
"""

from app.services.agents.base_agent import BaseAgent, AgentDecision, Action

__all__ = ['BaseAgent', 'AgentDecision', 'Action']

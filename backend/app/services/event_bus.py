"""
Event Bus for Agent Communication

Simple in-memory event pub/sub system for autonomous agents.
Can be upgraded to Redis Pub/Sub for distributed systems later.

Events:
- inventory.low_stock: When inventory falls below reorder level
- inventory.expiring_soon: When perishables are near expiry
- revenue.anomaly: When revenue deviates significantly
- kitchen.bottleneck: When kitchen prep time exceeds threshold
"""

import logging
from typing import Callable, Dict, List, Any
import asyncio

logger = logging.getLogger(__name__)


class EventBus:
    """
    In-memory event bus for agent communication

    Usage:
        event_bus = EventBus()

        # Subscribe to events
        async def handle_low_stock(data):
            print(f"Low stock alert: {data}")

        event_bus.subscribe('inventory.low_stock', handle_low_stock)

        # Publish events
        await event_bus.publish('inventory.low_stock', {
            'material_id': 'RM001',
            'current_stock': 5,
            'reorder_level': 10
        })
    """

    def __init__(self):
        """Initialize event bus with empty subscribers"""
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_history: List[Dict[str, Any]] = []
        self._max_history = 100  # Keep last 100 events

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        Subscribe a handler to an event type

        Args:
            event_type: Event name (e.g., 'inventory.low_stock')
            handler: Async function to call when event is published
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.info(f"Subscribed handler to event: {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """
        Unsubscribe a handler from an event type

        Args:
            event_type: Event name
            handler: Handler function to remove
        """
        if event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.info(f"Unsubscribed handler from event: {event_type}")

    async def publish(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Publish an event to all subscribers

        Args:
            event_type: Event name
            event_data: Event payload
        """
        logger.info(f"Publishing event: {event_type}")

        # Store in history
        self._event_history.append({
            'event_type': event_type,
            'data': event_data,
            'timestamp': asyncio.get_event_loop().time()
        })

        # Trim history if needed
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Call all subscribers
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                try:
                    await handler(event_data)
                except Exception as e:
                    logger.error(
                        f"Error in event handler for {event_type}: {e}",
                        exc_info=True
                    )

    def get_history(self, event_type: str = None, limit: int = 50) -> List[Dict]:
        """
        Get recent event history

        Args:
            event_type: Filter by event type (optional)
            limit: Max number of events to return

        Returns:
            List of recent events
        """
        if event_type:
            filtered = [e for e in self._event_history if e['event_type'] == event_type]
            return filtered[-limit:]
        return self._event_history[-limit:]

    def clear_history(self) -> None:
        """Clear event history"""
        self._event_history = []
        logger.info("Event history cleared")

    def get_subscriber_count(self, event_type: str = None) -> int:
        """
        Get number of subscribers

        Args:
            event_type: Specific event type, or None for all

        Returns:
            Number of subscribers
        """
        if event_type:
            return len(self._subscribers.get(event_type, []))
        return sum(len(handlers) for handlers in self._subscribers.values())


# Global event bus instance (singleton)
_event_bus_instance = None


def get_event_bus() -> EventBus:
    """
    Get global event bus instance (singleton pattern)

    Returns:
        Global EventBus instance
    """
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance

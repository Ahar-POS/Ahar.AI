"""
Unit tests for EventBus service

Tests:
- Event subscription and unsubscription
- Event publishing and handler execution
- Event history tracking
- Error handling in event handlers
- Singleton pattern
"""

import pytest
from app.services.event_bus import EventBus, get_event_bus


@pytest.mark.asyncio
async def test_event_subscription():
    """Test subscribing to events"""
    event_bus = EventBus()

    handler_called = False
    received_data = None

    async def test_handler(data):
        nonlocal handler_called, received_data
        handler_called = True
        received_data = data

    # Subscribe handler
    event_bus.subscribe('test.event', test_handler)

    # Verify subscription
    assert event_bus.get_subscriber_count('test.event') == 1

    # Publish event
    test_data = {'message': 'Hello from test'}
    await event_bus.publish('test.event', test_data)

    # Verify handler was called
    assert handler_called is True
    assert received_data == test_data


@pytest.mark.asyncio
async def test_event_unsubscription():
    """Test unsubscribing from events"""
    event_bus = EventBus()

    handler_called = False

    async def test_handler(data):
        nonlocal handler_called
        handler_called = True

    # Subscribe and then unsubscribe
    event_bus.subscribe('test.event', test_handler)
    event_bus.unsubscribe('test.event', test_handler)

    # Publish event
    await event_bus.publish('test.event', {'test': 'data'})

    # Handler should NOT have been called
    assert handler_called is False
    assert event_bus.get_subscriber_count('test.event') == 0


@pytest.mark.asyncio
async def test_multiple_subscribers():
    """Test multiple handlers for same event"""
    event_bus = EventBus()

    call_count = 0

    async def handler1(data):
        nonlocal call_count
        call_count += 1

    async def handler2(data):
        nonlocal call_count
        call_count += 1

    # Subscribe two handlers
    event_bus.subscribe('test.event', handler1)
    event_bus.subscribe('test.event', handler2)

    # Verify subscriber count
    assert event_bus.get_subscriber_count('test.event') == 2

    # Publish event
    await event_bus.publish('test.event', {})

    # Both handlers should be called
    assert call_count == 2


@pytest.mark.asyncio
async def test_event_history():
    """Test event history tracking"""
    event_bus = EventBus()

    # Publish multiple events
    await event_bus.publish('event.one', {'id': 1})
    await event_bus.publish('event.two', {'id': 2})
    await event_bus.publish('event.one', {'id': 3})

    # Get all history
    all_history = event_bus.get_history()
    assert len(all_history) == 3

    # Get filtered history
    event_one_history = event_bus.get_history(event_type='event.one')
    assert len(event_one_history) == 2
    assert event_one_history[0]['data']['id'] == 1
    assert event_one_history[1]['data']['id'] == 3

    # Test limit
    limited_history = event_bus.get_history(limit=2)
    assert len(limited_history) == 2


@pytest.mark.asyncio
async def test_event_history_max_size():
    """Test that event history is capped at max size"""
    event_bus = EventBus()
    event_bus._max_history = 5  # Set small limit for testing

    # Publish more events than max
    for i in range(10):
        await event_bus.publish('test.event', {'id': i})

    # Should only keep last 5
    history = event_bus.get_history()
    assert len(history) == 5
    assert history[0]['data']['id'] == 5  # Oldest kept
    assert history[-1]['data']['id'] == 9  # Newest


@pytest.mark.asyncio
async def test_handler_error_handling():
    """Test that errors in handlers don't crash the event bus"""
    event_bus = EventBus()

    handler2_called = False

    async def failing_handler(data):
        raise ValueError("Intentional test error")

    async def working_handler(data):
        nonlocal handler2_called
        handler2_called = True

    # Subscribe both handlers
    event_bus.subscribe('test.event', failing_handler)
    event_bus.subscribe('test.event', working_handler)

    # Publish event - should not crash
    await event_bus.publish('test.event', {})

    # Working handler should still be called despite error in first handler
    assert handler2_called is True


@pytest.mark.asyncio
async def test_clear_history():
    """Test clearing event history"""
    event_bus = EventBus()

    # Add some events
    await event_bus.publish('test.event', {'id': 1})
    await event_bus.publish('test.event', {'id': 2})

    # Verify history exists
    assert len(event_bus.get_history()) == 2

    # Clear history
    event_bus.clear_history()

    # Verify history is empty
    assert len(event_bus.get_history()) == 0


@pytest.mark.asyncio
async def test_singleton_pattern():
    """Test that get_event_bus returns same instance"""
    bus1 = get_event_bus()
    bus2 = get_event_bus()

    # Should be same instance
    assert bus1 is bus2

    # Subscribe on one, should reflect on other
    async def test_handler(data):
        pass

    bus1.subscribe('test.event', test_handler)
    assert bus2.get_subscriber_count('test.event') == 1


@pytest.mark.asyncio
async def test_publish_without_subscribers():
    """Test publishing event with no subscribers doesn't error"""
    event_bus = EventBus()

    # Should not raise error
    await event_bus.publish('nonexistent.event', {'data': 'test'})

    # Should be in history
    history = event_bus.get_history(event_type='nonexistent.event')
    assert len(history) == 1


@pytest.mark.asyncio
async def test_duplicate_subscription():
    """Test that subscribing same handler twice doesn't create duplicates"""
    event_bus = EventBus()

    call_count = 0

    async def test_handler(data):
        nonlocal call_count
        call_count += 1

    # Subscribe same handler twice
    event_bus.subscribe('test.event', test_handler)
    event_bus.subscribe('test.event', test_handler)

    # Should only be one subscriber
    assert event_bus.get_subscriber_count('test.event') == 1

    # Publish event
    await event_bus.publish('test.event', {})

    # Handler should only be called once
    assert call_count == 1

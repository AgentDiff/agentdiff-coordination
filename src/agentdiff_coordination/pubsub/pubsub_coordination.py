"""
Simple pub/sub functions for AgentDiff coordination

Provides the basic publish/subscribe functions used by the @when decorator
and emit() function.
"""

from typing import Callable, Any, Optional
from .pubsub_broker import _get_default_broker, EmbeddedBroker, Message


def _subscribe_to_event(
    topic: str,
    handler: Callable[[Message], None],
    broker: Optional[EmbeddedBroker] = None,
) -> str:
    """
    Subscribe to an event topic.

    Used internally by the @when decorator.

    Args:
        topic: Event topic to subscribe to
        handler: Function to call when event is received
        broker: Optional custom broker (uses default if None)

    Returns:
        subscriber_id: ID for unsubscribing later
    """
    broker = broker or _get_default_broker()
    return broker.subscribe(topic, handler)


def _publish_event(
    topic: str,
    data: Any,
    sender: Optional[str] = None,
    broker: Optional[EmbeddedBroker] = None,
) -> str:
    """
    Publish an event to a topic.

    Used internally by the emit() function.

    Args:
        topic: Event topic to publish to
        data: Event payload data
        sender: Optional sender identification
        broker: Optional custom broker (uses default if None)

    Returns:
        message_id: ID of the published message
    """
    broker = broker or _get_default_broker()
    return broker.publish(topic, data, sender)


def _unsubscribe_from_event(
    topic: str, subscriber_id: str, broker: Optional[EmbeddedBroker] = None
) -> bool:
    """
    Unsubscribe from an event topic.

    Args:
        topic: Event topic to unsubscribe from
        subscriber_id: ID returned by _subscribe_to_event()
        broker: Optional custom broker (uses default if None)

    Returns:
        bool: True if successfully unsubscribed
    """
    broker = broker or _get_default_broker()
    return broker.unsubscribe(topic, subscriber_id)


def _cleanup_all_events(broker: Optional[EmbeddedBroker] = None) -> int:
    """
    Cleanup all event subscriptions.

    Args:
        broker: Optional custom broker (uses default if None)

    Returns:
        int: Number of subscriptions cleaned up
    """
    broker = broker or _get_default_broker()
    return broker.unsubscribe_all()

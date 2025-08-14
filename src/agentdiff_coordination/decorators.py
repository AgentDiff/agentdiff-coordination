"""
Decorator-Based Coordination API

Provides @coordinate, @when decorators and emit() function
for intuitive agent coordination.
"""

import time
import wrapt
from typing import Callable, Any, Optional

from .coordination import AgentLock
from .pubsub.pubsub_coordination import (
    _subscribe_to_event,
    _publish_event,
    _unsubscribe_from_event,
    _cleanup_all_events,
)
from .logging import get_logger, get_monitor


def lock(resource_name: str, timeout: Optional[float] = None):
    """
    Decorator to protect function with resource lock

    Usage:
        @lock("database")
        def update_records():
            # Only one agent can execute this at a time
            pass

        @lock("openai_api")
        def call_llm():
            # Prevent API rate limiting
            pass
    """

    @wrapt.decorator
    def wrapper(wrapped, instance, args, kwargs):
        with AgentLock(resource_name, timeout=timeout):
            return wrapped(*args, **kwargs)

    return wrapper


def when(event_name: str, timeout: Optional[float] = None):
    """
    Decorator to register function as event handler

    Usage:
        @when("research_complete")
        def handle_research(event_data):
            # Called when research_complete event occurs
            pass
    """

    @wrapt.decorator
    def wrapper(wrapped, instance, args, kwargs):
        # The original function is called directly with event data
        # This wrapper preserves function metadata and allows normal function calls
        return wrapped(*args, **kwargs)

    def decorator(func: Callable) -> Callable:
        def event_handler(message):
            try:
                event_data = message.payload
                return func(event_data)
            except Exception as handler_error:
                # Log the error in the event handler
                # Use a separate logger for event handling errors
                logger = get_logger("events")
                logger.error(
                    f"Event handler {func.__name__} failed for event {event_name}: {handler_error}"
                )
                # Re-raise to trigger retry mechanism - subscriber wrapper expects exceptions
                raise handler_error

        # Subscribe to the event (note: timeout handled by broker, not subscription)
        subscriber_id = _subscribe_to_event(event_name, event_handler)

        # Apply wrapt decorator to preserve metadata
        wrapped_func = wrapper(func)

        # Store subscription info on wrapped function for potential cleanup
        wrapped_func._agentdiff_subscription = {
            "event_name": event_name,
            "subscriber_id": subscriber_id,
            "original_function": func,
        }

        return wrapped_func

    return decorator


def emit(event_name: str, data: Any = None, sender: Optional[str] = None):
    """
    Emit an event to trigger registered handlers

    Usage:
        emit("research_complete", {"findings": results})
        emit("workflow_started")
        emit("agent_failed", {"error": "timeout"}, sender="research_agent")
    """
    return _publish_event(topic=event_name, data=data, sender=sender)


# Main coordination decorator
def coordinate(name: str, lock_name: Optional[str] = None):
    """
    AgentDiff coordination decorator for agent functions.

    Provides:
    - Resource protection via locks (if lock_name specified)
    - Automatic lifecycle events: {name}_started, {name}_complete, {name}_failed
    - Production logging and monitoring
    - Event-driven coordination

    Usage:
        @coordinate("researcher", lock_name="openai_api")
        def research_agent(topic):
            # Automatically protected by "openai_api" lock and emits lifecycle events
            return do_research(topic)
    """

    @wrapt.decorator
    def wrapper(wrapped, instance, args, kwargs):
        agent_name = name
        logger = get_logger("agents")
        monitor = get_monitor()

        start_time = time.perf_counter()  # Monotonic time for duration measurement
        wall_time = time.time()  # Wall clock time for timestamps

        # Log and monitor agent start
        logger.agent_started(agent_name, function=wrapped.__name__, lock_name=lock_name)
        monitor.record_agent_start(agent_name)

        # Always emit start event
        emit(
            f"{agent_name}_started",
            {
                "args": args,
                "kwargs": kwargs,
                "timestamp": wall_time,
            },
            sender=agent_name,
        )

        try:
            # Acquire lock if specified
            if lock_name:
                lock_start = time.perf_counter()
                logger.resource_locked(lock_name, agent_name)
                with AgentLock(lock_name):
                    result = wrapped(*args, **kwargs)
                lock_duration = time.perf_counter() - lock_start
                logger.resource_released(lock_name, agent_name, lock_duration)
            else:
                # No lock, just call the function directly
                result = wrapped(*args, **kwargs)

            # Calculate duration and log completion
            duration = time.perf_counter() - start_time
            logger.agent_completed(agent_name, duration, function=wrapped.__name__)
            monitor.record_agent_completion(agent_name, duration)

            # Always emit completion event
            emit(
                f"{agent_name}_complete",
                {
                    "result": result,
                    "timestamp": time.time(),
                    "duration": duration,
                },
                sender=agent_name,
            )

            return result

        except Exception as e:

            duration = time.perf_counter() - start_time

            try:
                # Log failure and emit failure event
                logger.agent_failed(agent_name, e, duration, function=wrapped.__name__)
                monitor.record_agent_failure(agent_name, e, duration)
                emit(
                    f"{agent_name}_failed",
                    {
                        "error": str(e),
                        "timestamp": time.time(),
                        "duration": duration,
                    },
                    sender=agent_name,
                )
            except Exception as coord_error:
                # Log coordination failure, but preserve original agent exception
                logger.error(f"Coordination infrastructure failed: {coord_error}")
            raise

    return wrapper


# Context managers for when decorators aren't suitable
class LockContext:
    """Context manager version of @lock"""

    def __init__(self, resource_name: str, timeout: Optional[float] = None):
        self.resource_name = resource_name
        self.timeout = timeout

    def __enter__(self):
        self._lock = AgentLock(self.resource_name, timeout=self.timeout)
        return self._lock.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._lock.__exit__(exc_type, exc_val, exc_tb)


# Convenience functions for context managers
def lock_context(resource_name: str, timeout: Optional[float] = None):
    """Create lock context manager"""
    return LockContext(resource_name, timeout)


# Cleanup utilities
def unsubscribe_function(func: Callable) -> bool:
    """Unsubscribe a function decorated with @when"""
    if hasattr(func, "_agentdiff_subscription"):
        subscription = func._agentdiff_subscription
        event_name = subscription["event_name"]
        subscriber_id = subscription["subscriber_id"]

        # Actually unsubscribe from the pubsub layer
        success = _unsubscribe_from_event(event_name, subscriber_id)

        # Clear subscription info regardless of success
        delattr(func, "_agentdiff_subscription")
        return success
    return False


def cleanup_all_subscriptions() -> int:
    """
    Cleanup all event subscriptions (for testing/shutdown).

    Returns:
        int: Number of subscriptions cleaned up
    """
    return _cleanup_all_events()

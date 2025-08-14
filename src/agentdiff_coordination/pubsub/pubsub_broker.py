"""
Embedded Pub/Sub Broker for AI Agent Coordination

Provides reliable message passing without external dependencies.
Designed to be lightweight and fast.
"""

import threading
import queue
import time
import os
import json
import logging
import fnmatch
import heapq
import itertools
import atexit
from typing import Dict, List, Callable, Any, Optional, Set
from dataclasses import dataclass, asdict
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, TimeoutError
import concurrent.futures as cf
import uuid

# Import persistence backends
from ..persistence.redis_persistence import RedisPersistence
from ..persistence.file_persistence import FilePersistence
from ..config import config

logger = logging.getLogger(__name__)


def _run_callback(callback, message):
    return callback(message)


def _new_msg_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Message:
    """Message structure for pub/sub system"""

    topic: str
    payload: Any
    timestamp: float
    message_id: str
    sender: Optional[str] = None
    correlation_id: Optional[str] = None
    retry_count: int = 0


class CircuitBreaker:
    """Circuit breaker to isolate failing subscribers"""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._half_open_attempted = False  # Track HALF_OPEN trial
        self._lock = threading.RLock()

    def can_execute(self) -> bool:
        """Check if operation can be executed"""
        with self._lock:
            if self.state == "CLOSED":
                return True
            elif self.state == "OPEN":
                if time.perf_counter() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    self._half_open_attempted = False
                    return True
                return False
            else:  # HALF_OPEN - only allow one trial
                if not self._half_open_attempted:
                    self._half_open_attempted = True
                    return True
                return False

    def record_success(self):
        """Record successful operation"""
        with self._lock:
            self.failure_count = 0
            self.state = "CLOSED"
            self._half_open_attempted = False

    def record_failure(self):
        """Record failed operation"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.perf_counter()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(
                    f"Circuit breaker opened after {self.failure_count} failures"
                )


class SubscriberWrapper:
    """Wrapper for subscriber callbacks with reliability features"""

    def __init__(
        self,
        callback: Callable,
        topic: str,
        subscriber_id: str,
        timeout: float = 30.0,
        mode: str = "thread",
        max_workers: int = 1,
    ):
        self.callback = callback
        self.topic = topic
        self.subscriber_id = subscriber_id
        self.timeout = timeout
        self.mode = mode
        self.circuit_breaker = CircuitBreaker()
        self.total_messages = 0
        self.successful_messages = 0
        self.failed_messages = 0
        self.last_activity = time.perf_counter()
        self._lock = threading.RLock()
        self._exec = (
            ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix=f"sub-{subscriber_id}"
            )
            if mode == "thread"
            else ProcessPoolExecutor(max_workers=max_workers)
        )

    def execute(self, message: Message) -> bool:
        """Execute callback with timeout and circuit breaker"""
        if not self.circuit_breaker.can_execute():
            logger.debug(
                f"Circuit breaker open for {self.subscriber_id} on topic {self.topic}"
            )
            return False

        with self._lock:
            self.total_messages += 1
            self.last_activity = time.perf_counter()

        try:
            fut = (
                self._exec.submit(self.callback, message)
                if self.mode == "thread"
                else self._exec.submit(_run_callback, self.callback, message)
            )
            fut.result(timeout=self.timeout)  # raises TimeoutError on timeout
            self.circuit_breaker.record_success()

            with self._lock:
                self.successful_messages += 1

            return True

        except RuntimeError as e:
            if "cannot schedule new futures after interpreter shutdown" in str(e):
                # Interpreter is shutting down, silently ignore
                logger.debug(f"Subscriber {self.subscriber_id} ignoring message during shutdown")
                return False
            else:
                # Re-raise other RuntimeErrors
                raise

        except TimeoutError:
            logger.warning(
                f"Subscriber {self.subscriber_id} timeout on topic {self.topic}"
            )
            self.circuit_breaker.record_failure()

            with self._lock:
                self.failed_messages += 1

            # For process mode, the worker can be replaced if needed
            return False

        except Exception as e:
            logger.exception(
                f"Subscriber {self.subscriber_id} failed on topic {self.topic}: {e}"
            )
            self.circuit_breaker.record_failure()

            with self._lock:
                self.failed_messages += 1

            return False

    @property
    def health_score(self) -> float:
        """Calculate health score (0.0 to 1.0)"""
        with self._lock:
            if self.total_messages == 0:
                return 1.0
            return self.successful_messages / self.total_messages

    @property
    def is_healthy(self) -> bool:
        """Check if subscriber is healthy"""
        return (
            self.circuit_breaker.state == "CLOSED"
            and self.health_score > 0.5
            and time.perf_counter() - self.last_activity < 300
        )  # 5 minutes

    def shutdown(self):
        """Explicit cleanup"""
        try:
            self._exec.shutdown(wait=False)  # Don't wait indefinitely
            logger.debug(f"Subscriber {self.subscriber_id} executor shutdown")
        except Exception as e:
            logger.error(f"Error shutting down subscriber {self.subscriber_id}: {e}")


class EmbeddedBroker:
    """Embedded pub/sub broker."""

    def __init__(
        self,
        persistence_backend: str = "file",
        persistence_config: Optional[Dict[str, Any]] = None,
        max_workers: int = 10,
        queue_maxsize: int = 10000,
    ):
        """
        Initialize EmbeddedBroker with explicit backend selection.

        Args:
            persistence_backend: "file", "redis", "kafka", or "none"
            persistence_config: Backend-specific configuration
            max_workers: Thread pool size
        """

        # Core pub/sub state - dictionary-based channel management
        self._subscribers: Dict[str, Dict[str, SubscriberWrapper]] = defaultdict(dict)
        self._pattern_subscribers: Dict[str, Dict[str, SubscriberWrapper]] = (
            defaultdict(dict)
        )  # Pattern subscribers for wildcard topics
        self._dead_letter_queue = queue.Queue(maxsize=1000)
        self._lock = threading.RLock()

        self._dispatch_q = queue.Queue(maxsize=queue_maxsize)
        self._running = True

        self._dispatchers = []
        for _ in range(max(1, min(4, max_workers // 2))):
            t = threading.Thread(target=self._dispatch_loop, daemon=True)
            t.start()
            self._dispatchers.append(t)

        self._thread_pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="broker"
        )

        # Retry mechanism
        self._retry_heap = []  # (ready_ts, seq, subscriber, message, attempt)
        self._retry_heap_max = 1000  # Limit size to prevent memory bloat
        self._seq = itertools.count()
        self._max_retries = 5
        self._base_backoff = 0.5

        self._attempts: Dict[tuple[str, str], int] = {}
        self._attempts_lock = threading.RLock()
        self._retry_lock = threading.RLock()  # Guard the retry heap for thread safety

        self._retry_thread = threading.Thread(target=self._retry_loop, daemon=True)
        self._retry_thread.start()

        # Initialize health monitoring attributes first
        self._stop_evt = threading.Event()
        self._message_count = 0
        self._start_time = time.perf_counter()
        self._health_check_interval = 60  # seconds

        # Initialize persistence backend
        self._persistence = None
        self._persistence_backend = persistence_backend.lower()
        self._persistence_config = persistence_config or {}

        if self._persistence_backend != "none":
            self._initialize_persistence()

        # Start health monitoring thread after attributes are initialized
        self._health_thread = threading.Thread(target=self._health_monitor, daemon=True)
        self._health_thread.start()

        # Cleanup on startup if persistence is enabled
        if self._persistence:
            try:
                self._persistence.cleanup_old_data()
            except AttributeError:
                # Some backends might not have cleanup_old_data
                pass
            except Exception as e:
                logger.warning(f"Failed to initialize persistence: {e}")
                logger.warning("Continuing with in-memory only")

    def _initialize_persistence(self):
        """Initialize the selected persistence backend"""
        try:
            if self._persistence_backend == "file":
                # Use central config data_dir, with fallback override from persistence_config
                persistence_dir = self._persistence_config.get("dir") or config.data_dir
                self._persistence = FilePersistence(persistence_dir)
                logger.info(
                    f"File persistence enabled: {self._persistence.session_file}"
                )

            elif self._persistence_backend == "redis":
                # Use central config values with fallback overrides from persistence_config
                redis_config = {
                    "redis_url": self._persistence_config.get("redis_url")
                    or config.redis_url,
                    "redis_password": self._persistence_config.get("redis_password")
                    or config.redis_password,
                    "redis_db": self._persistence_config.get(
                        "redis_db", config.redis_db
                    ),
                    "key_prefix": self._persistence_config.get("key_prefix")
                    or config.redis_prefix,
                    "fallback_to_file": self._persistence_config.get(
                        "fallback_to_file", True
                    ),
                }

                self._persistence = RedisPersistence(**redis_config)
                logger.info(f"Redis persistence enabled: {redis_config['redis_url']}")

            elif self._persistence_backend == "kafka":
                # Future: Kafka implementation
                raise NotImplementedError(
                    "Kafka persistence backend not yet implemented"
                )

            else:
                raise ValueError(
                    f"Unknown persistence backend: {self._persistence_backend}"
                )

        except Exception as e:
            logger.error(
                f"Failed to initialize {self._persistence_backend} persistence: {e}"
            )

            # Fallback to file persistence if enabled
            if (
                self._persistence_config.get("fallback_to_file", True)
                and self._persistence_backend != "file"
            ):
                logger.info("Falling back to file persistence")
                try:
                    persistence_dir = config.data_dir
                    self._persistence = FilePersistence(persistence_dir)
                    logger.info(
                        f"File persistence fallback enabled: {self._persistence.session_file}"
                    )
                except Exception as fallback_error:
                    logger.error(
                        f"File persistence fallback also failed: {fallback_error}"
                    )
                    logger.warning("Running with in-memory only - no persistence")
            else:
                logger.warning("Running with in-memory only - no persistence")
        # Health monitoring already started in __init__

    def _health_monitor(self):
        """Background health monitoring"""
        while not self._stop_evt.wait(self._health_check_interval):
            try:
                self._check_subscriber_health()
            except Exception:
                logger.exception("Health monitor error")

    def _dispatch_loop(self):
        """Dispatch loop for processing messages from the queue."""
        while self._running or not self._dispatch_q.empty():
            try:
                sub, msg = self._dispatch_q.get(timeout=0.5)
            except queue.Empty:
                continue
            self._deliver_message(sub, msg)
            self._dispatch_q.task_done()

    def _retry_loop(self):
        """Retry loop for handling failed message deliveries"""
        while self._running:
            now = time.perf_counter()
            ready_retries = []

            # Collect ready retries
            with self._retry_lock:
                while self._retry_heap and self._retry_heap[0][0] <= now:
                    _, _, sub, msg, _ = heapq.heappop(self._retry_heap)
                    ready_retries.append((sub, msg))

            # Enqueue outside lock to avoid convoy effects
            for sub, msg in ready_retries:
                self._enqueue_dispatch(sub, msg)

            time.sleep(0.1)

    def _enqueue_dispatch(self, subscriber, message):
        """Enqueue message for dispatch"""
        try:
            # Use non-blocking put to avoid deadlocks
            self._dispatch_q.put_nowait((subscriber, message))
        except queue.Full:
            # If dispatch queue is full, send to dead letter queue
            logger.warning("Dispatch queue full; sending to DLQ")
            try:
                self._dead_letter_queue.put_nowait(
                    {
                        "message": message,
                        "subscriber_id": subscriber.subscriber_id,
                        "failure_time": time.time(),
                        "reason": "queue_full",
                    }
                )
            except queue.Full:
                # DLQ also full - log and drop completely
                logger.error(
                    f"DLQ full, dropping message {message.message_id} from dispatch queue overflow"
                )

    def _check_subscriber_health(self):
        """Check health of all subscribers"""
        with self._lock:
            unhealthy_count = 0
            total_count = 0

            for topic, subscribers_dict in self._subscribers.items():
                for subscriber in subscribers_dict.values():
                    total_count += 1
                    if not subscriber.is_healthy:
                        unhealthy_count += 1
                        logger.warning(
                            f"Unhealthy subscriber {subscriber.subscriber_id} on topic {topic}: "
                            f"health_score={subscriber.health_score:.2f}, "
                            f"circuit_breaker={subscriber.circuit_breaker.state}"
                        )

            if total_count > 0:
                health_ratio = (total_count - unhealthy_count) / total_count
                logger.debug(
                    f"Subscriber health: {health_ratio:.1%} ({total_count - unhealthy_count}/{total_count})"
                )

    def subscribe(
        self,
        topic: str,
        callback: Callable[[Message], None],
        subscriber_id: Optional[str] = None,
        timeout: float = 30.0,
    ) -> str:
        """
        Subscribe to a topic

        Args:
            topic: Topic to subscribe to (supports wildcards like 'agent.*')
            callback: Function to call when message received
            subscriber_id: Unique ID for this subscriber (auto-generated if None)
            timeout: Timeout for callback execution

        Returns:
            subscriber_id for unsubscribing later
        """
        if subscriber_id is None:
            subscriber_id = uuid.uuid4().hex

        wrapper = SubscriberWrapper(callback, topic, subscriber_id, timeout)

        with self._lock:
            if "*" in topic or "?" in topic:
                self._pattern_subscribers[topic][subscriber_id] = wrapper
            else:
                self._subscribers[topic][subscriber_id] = wrapper

        logger.debug(f"Subscribed {subscriber_id} to topic '{topic}'")
        return subscriber_id

    def unsubscribe(self, topic: str, subscriber_id: str) -> bool:
        """Unsubscribe from a topic"""
        with self._lock:
            # Check exact topic subscribers
            if topic in self._subscribers:
                wrapper = self._subscribers[topic].pop(subscriber_id, None)
                if wrapper:
                    # Cleanup empty dictionaries automatically
                    if not self._subscribers[topic]:
                        del self._subscribers[topic]
                    # Cleanup subscriber resources¯
                    wrapper.shutdown()
                    logger.debug(f"Unsubscribed {subscriber_id} from topic '{topic}'")
                    return True

            # Check pattern subscribers
            if topic in self._pattern_subscribers:
                wrapper = self._pattern_subscribers[topic].pop(subscriber_id, None)
                if wrapper:
                    # Cleanup empty dictionaries automatically
                    if not self._pattern_subscribers[topic]:
                        del self._pattern_subscribers[topic]
                    # Cleanup subscriber resources
                    wrapper.shutdown()
                    logger.debug(f"Unsubscribed {subscriber_id} from pattern '{topic}'")
                    return True

        return False

    def publish(
        self,
        topic: str,
        payload: Any,
        sender: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        Publish message to topic

        Args:
            topic: Topic to publish to
            payload: Message payload (any JSON-serializable data)
            sender: Optional sender identification
            correlation_id: Optional correlation ID for request/response patterns

        Returns:
            message_id of published message
        """
        # Guard against publish after shutdown
        if not self._running:
            logger.warning("Publish called after shutdown; dropping")
            return _new_msg_id()

        # Create message
        message = Message(
            topic=topic,
            payload=payload,
            timestamp=time.time(),
            message_id=_new_msg_id(),
            sender=sender,
            correlation_id=correlation_id,
        )

        # Persist message (async)
        if self._persistence:
            self._thread_pool.submit(self._persistence.store_message, message)

        # Find subscribers
        subscribers = self._find_subscribers(topic)

        if not subscribers:
            logger.debug(f"No subscribers for topic '{topic}'")
            return message.message_id

        # Deliver to subscribers
        for subscriber in subscribers:
            self._enqueue_dispatch(subscriber, message)

        with self._lock:
            self._message_count += 1

        logger.debug(
            f"Published message {message.message_id} to topic '{topic}' ({len(subscribers)} subscribers)"
        )
        return message.message_id

    def _find_subscribers(self, topic: str) -> List[SubscriberWrapper]:
        """Find all subscribers for a topic"""
        subscribers = []

        with self._lock:
            # Exact topic match
            if topic in self._subscribers:
                subscribers.extend(self._subscribers[topic].values())

            # Pattern matches
            for pattern, pattern_subs_dict in self._pattern_subscribers.items():
                if fnmatch.fnmatch(topic, pattern):
                    subscribers.extend(pattern_subs_dict.values())

        return subscribers

    def _deliver_message(self, subscriber: SubscriberWrapper, message: Message):
        """Deliver message to subscriber with retry mechanism"""
        key = (subscriber.subscriber_id, message.message_id)
        success = False

        try:
            success = subscriber.execute(message)
        except Exception as e:
            logger.exception(
                f"Fatal error delivering message to {subscriber.subscriber_id}: {e}"
            )

        if success:
            # Clear attempt tracking on success
            with self._attempts_lock:
                self._attempts.pop(key, None)
            return

        # Track attempts per (subscriber, message) to avoid Message object races
        with self._attempts_lock:
            attempt = self._attempts.get(key, 0) + 1
            self._attempts[key] = attempt

        if attempt <= self._max_retries:
            backoff = min(self._base_backoff * (2 ** (attempt - 1)), 30.0)

            # Thread-safe retry heap operations
            with self._retry_lock:
                if len(self._retry_heap) >= self._retry_heap_max:
                    # Drop earliest-due retries to keep latency bounded
                    drop = max(1, self._retry_heap_max // 10)
                    for _ in range(min(drop, len(self._retry_heap))):
                        heapq.heappop(self._retry_heap)
                    logger.warning(f"Retry heap full, dropped {drop} retries")

                heapq.heappush(
                    self._retry_heap,
                    (
                        time.perf_counter() + backoff,
                        next(self._seq),
                        subscriber,
                        message,
                        attempt,
                    ),
                )
        else:
            # Send to DLQ after max retries
            dlq_entry = {
                "message": message,
                "subscriber_id": subscriber.subscriber_id,
                "failure_time": time.time(),
                "reason": "max_retries_exceeded",
                "retry_count": attempt,  # Use tracked attempt count, not message.retry_count
            }

            try:
                self._dead_letter_queue.put_nowait(dlq_entry)
            except queue.Full:
                logger.error(f"DLQ full, dropping failed message {message.message_id}")

            # Persist DLQ entry if persistence enabled
            if self._persistence and hasattr(self._persistence, "store_dead_letter"):
                try:
                    self._persistence.store_dead_letter(dlq_entry)
                except Exception as e:
                    logger.error(f"Failed to persist dead letter: {e}")

            # Clean up attempt tracking
            with self._attempts_lock:
                self._attempts.pop(key, None)

    def get_stats(self) -> Dict[str, Any]:
        """Get broker statistics"""
        with self._lock:
            subscriber_count = sum(
                len(subs_dict) for subs_dict in self._subscribers.values()
            )
            pattern_subscriber_count = sum(
                len(subs_dict) for subs_dict in self._pattern_subscribers.values()
            )

            return {
                "uptime_seconds": time.perf_counter() - self._start_time,
                "total_messages": self._message_count,
                "subscribers": subscriber_count,
                "pattern_subscribers": pattern_subscriber_count,
                "dead_letters": self._dead_letter_queue.qsize(),
                "persistence_enabled": self._persistence is not None,
                "persistence_file": (
                    getattr(self._persistence, "session_file", None)
                    if self._persistence
                    else None
                ),
            }

    def _get_dead_letters(self) -> List[Dict[str, Any]]:
        """Get messages from dead letter queue"""
        dead_letters = []
        try:
            while True:
                dead_letter = self._dead_letter_queue.get_nowait()
                dead_letters.append(dead_letter)
        except queue.Empty:
            pass

        return dead_letters

    def _get_all_subscribers(self) -> List[Dict[str, str]]:
        """Get all active subscribers for cleanup/debugging"""
        subscribers = []

        with self._lock:
            # Exact topic subscribers
            for topic, subs_dict in self._subscribers.items():
                for sub_id, wrapper in subs_dict.items():
                    subscribers.append(
                        {"subscriber_id": sub_id, "topic": topic, "type": "exact"}
                    )

            # Pattern subscribers
            for pattern, subs_dict in self._pattern_subscribers.items():
                for sub_id, wrapper in subs_dict.items():
                    subscribers.append(
                        {"subscriber_id": sub_id, "topic": pattern, "type": "pattern"}
                    )

        return subscribers

    def unsubscribe_all(self) -> int:
        """Unsubscribe all subscribers and return count"""
        count = 0

        with self._lock:
            # Unsubscribe exact topics
            for topic in list(self._subscribers.keys()):
                for sub_id in list(self._subscribers[topic].keys()):
                    if self.unsubscribe(topic, sub_id):
                        count += 1

            # Unsubscribe patterns
            for pattern in list(self._pattern_subscribers.keys()):
                for sub_id in list(self._pattern_subscribers[pattern].keys()):
                    if self.unsubscribe(pattern, sub_id):
                        count += 1

        return count

    def shutdown(self, timeout: float = 30.0):
        """Shutdown broker gracefully with timeout"""
        logger.info("Shutting down embedded broker")
        self._running = False

        # Clean up all subscribers
        with self._lock:
            for topic_subscribers in self._subscribers.values():
                for wrapper in topic_subscribers.values():
                    wrapper.shutdown()
            for pattern_subscribers in self._pattern_subscribers.values():
                for wrapper in pattern_subscribers.values():
                    wrapper.shutdown()
            self._subscribers.clear()
            self._pattern_subscribers.clear()

        # Stop health monitor
        self._stop_evt.set()
        self._health_thread.join(timeout=5)

        # Stop retry thread
        self._retry_thread.join(timeout=2)

        # Wait for dispatch queue to drain (with timeout)
        start_time = time.perf_counter()
        while not self._dispatch_q.empty() and time.perf_counter() - start_time < 10:
            time.sleep(0.1)

        # Join dispatcher threads for clean shutdown
        for dispatcher_thread in self._dispatchers:
            dispatcher_thread.join(timeout=2)

        # Shutdown thread pool
        try:
            # Don't cancel futures since we already drained the dispatch queue
            self._thread_pool.shutdown(wait=True, cancel_futures=False)
        except Exception as e:
            logger.error(f"Thread pool shutdown error: {e}")

        if self._persistence:
            self._persistence.cleanup_old_data()


# Global broker instance
_default_broker: Optional[EmbeddedBroker] = None
_broker_lock = threading.RLock()
_cleanup_registered = False


def _cleanup_default_broker():
    """Cleanup function to shutdown the default broker on exit"""
    global _default_broker
    if _default_broker is not None:
        try:
            _default_broker.shutdown(timeout=5.0)
        except Exception as e:
            # Use print instead of logger since logging may be shut down
            print(f"Warning: Error during broker shutdown: {e}")
        finally:
            _default_broker = None


def _get_default_broker() -> EmbeddedBroker:
    """Get or create the default global broker instance (file-based by default)"""
    global _default_broker, _cleanup_registered

    with _broker_lock:
        if _default_broker is None:
            # Register cleanup function on first broker creation
            if not _cleanup_registered:
                atexit.register(_cleanup_default_broker)
                _cleanup_registered = True
            # Use config for backend selection
            backend = config.persistence_backend

            if backend == "none" or config.disable_persistence:
                _default_broker = EmbeddedBroker(persistence_backend="none")
            elif backend == "redis":
                redis_config = {
                    "redis_url": config.redis_url,
                    "redis_password": config.redis_password,
                    "redis_db": config.redis_db,
                    "key_prefix": config.redis_prefix,
                    "fallback_to_file": True,
                }
                _default_broker = EmbeddedBroker(
                    persistence_backend="redis", persistence_config=redis_config
                )
            else:
                # Default to file backend
                file_config = {"dir": config.data_dir}
                _default_broker = EmbeddedBroker(
                    persistence_backend="file", persistence_config=file_config
                )
        return _default_broker


def configure_broker(backend: str = "file", **config) -> None:
    """
    Configure the global broker backend.

    Args:
        backend: "file", "redis", "inmemory", or "kafka"
        **config: Backend-specific configuration

    Examples:
        configure_broker("file", dir="/var/agentdiff")
        configure_broker("redis", url="redis://prod:6379", password="secret")
        configure_broker("inmemory")
        configure_broker("kafka", bootstrap_servers="kafka:9092")
    """
    global _default_broker

    with _broker_lock:
        # Shutdown existing broker if any
        if _default_broker is not None:
            try:
                _default_broker.shutdown()
            except Exception:
                pass

        # Create new broker with specified backend
        if backend == "file":
            _default_broker = EmbeddedBroker(
                persistence_backend="file", persistence_config=config
            )
        elif backend == "redis":
            _default_broker = EmbeddedBroker(
                persistence_backend="redis", persistence_config=config
            )
        elif backend == "inmemory":
            _default_broker = EmbeddedBroker(
                persistence_backend="none", persistence_config=config
            )
        elif backend == "kafka":
            _default_broker = EmbeddedBroker(
                persistence_backend="kafka", persistence_config=config
            )
        else:
            raise ValueError(f"Unknown backend: {backend}")

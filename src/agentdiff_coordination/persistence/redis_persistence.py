"""
Redis-based persistence for AgentDiff coordination system.

Provides Redis storage with automatic fallback to file-based persistence
for message and dead letter queue management.
Includes retry logic, connection management, and health status reporting.
"""

import json
import time
import threading
import logging
import uuid
from typing import Dict, Optional, Any

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from .persistence_interface import PersistenceBackend, Message
from .file_persistence import FilePersistence

logger = logging.getLogger(__name__)


class RedisPersistence(PersistenceBackend):
    """Redis-based persistence with automatic failover to filesystem"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        redis_password: Optional[str] = None,
        redis_db: int = 0,
        key_prefix: str = "agentdiff:",
        fallback_to_file: bool = True,
        connection_timeout: int = 5,
        retry_attempts: int = 3,
    ):
        self.redis_url = redis_url
        self.redis_password = redis_password
        self.redis_db = redis_db
        self.key_prefix = key_prefix
        self.fallback_to_file = fallback_to_file
        self.connection_timeout = connection_timeout
        self.retry_attempts = retry_attempts

        self._redis_client = None
        self._redis_available = False
        self._lock = threading.Lock()
        self._file_fallback = None

        # Initialize Redis connection
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection with fallback handling"""
        if not REDIS_AVAILABLE:
            if self.fallback_to_file:
                self._file_fallback = FilePersistence()
                logger.warning("Redis not available, using filesystem fallback")
            return

        try:
            # Parse Redis URL or create connection
            if self.redis_url.startswith("redis://") or self.redis_url.startswith(
                "rediss://"
            ):
                self._redis_client = redis.from_url(
                    self.redis_url,
                    password=self.redis_password,
                    db=self.redis_db,
                    socket_connect_timeout=self.connection_timeout,
                    socket_timeout=self.connection_timeout,
                    retry_on_timeout=True,
                    decode_responses=True,
                )
            else:
                # Assume host:port format
                host, port = self.redis_url.split(":")
                self._redis_client = redis.Redis(
                    host=host,
                    port=int(port),
                    password=self.redis_password,
                    db=self.redis_db,
                    socket_connect_timeout=self.connection_timeout,
                    socket_timeout=self.connection_timeout,
                    retry_on_timeout=True,
                    decode_responses=True,
                )

            # Test connection
            self._redis_client.ping()
            self._redis_available = True
            logger.info(f"Connected to Redis at {self.redis_url}")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            if self.fallback_to_file:
                self._file_fallback = FilePersistence()
                logger.info("Falling back to filesystem persistence")

    def _get_key(self, key: str) -> str:
        """Get prefixed Redis key"""
        return f"{self.key_prefix}{key}"

    def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute Redis operation with retry logic"""
        if not self._redis_available or not self._redis_client:
            if self._file_fallback:
                return getattr(self._file_fallback, operation.__name__)(*args, **kwargs)
            raise RuntimeError("Redis unavailable and no fallback configured")

        for attempt in range(self.retry_attempts):
            try:
                return operation(*args, **kwargs)
            except (redis.ConnectionError, redis.TimeoutError) as e:
                if attempt == self.retry_attempts - 1:
                    logger.error(
                        f"Redis operation failed after {self.retry_attempts} attempts: {e}"
                    )
                    if self._file_fallback:
                        logger.info("Using filesystem fallback")
                        return getattr(self._file_fallback, operation.__name__)(
                            *args, **kwargs
                        )
                    raise
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff

        raise RuntimeError("Should not reach here")

    def store_message(self, message: Message) -> bool:
        """Store message to Redis"""

        def _store():
            key = self._get_key(f"message:{message.message_id}")
            data = {
                "topic": message.topic,
                "payload": message.payload,
                "timestamp": message.timestamp,
                "message_id": message.message_id,
                "sender": message.sender,
                "correlation_id": message.correlation_id,
            }

            # Store message with TTL
            self._redis_client.setex(
                key, 3600, json.dumps(data, default=str)
            )  # 1 hour TTL

            # Also add to topic-specific list for replay
            topic_key = self._get_key(f"topic:{message.topic}")
            self._redis_client.lpush(topic_key, json.dumps(data, default=str))
            self._redis_client.ltrim(topic_key, 0, 99)  # Keep last 100 messages
            self._redis_client.expire(topic_key, 3600)

            return True

        try:
            return self._execute_with_retry(_store)
        except Exception:
            return False

    def store_dead_letter(self, entry: Dict[str, Any]) -> bool:
        """Store dead letter entry to Redis"""

        def _store():
            # Create a unique key for this dead letter entry
            dlq_id = uuid.uuid4().hex
            key = self._get_key(f"dlq:{dlq_id}")

            # Store with TTL
            self._redis_client.setex(
                key, 86400, json.dumps(entry, default=str)
            )  # 24 hour TTL

            # Also add to dead letter queue list
            dlq_key = self._get_key("dead_letters")
            self._redis_client.lpush(dlq_key, json.dumps(entry, default=str))
            self._redis_client.ltrim(dlq_key, 0, 999)  # Keep last 1000 dead letters
            self._redis_client.expire(dlq_key, 86400)  # 24 hour TTL

            return True

        try:
            return self._execute_with_retry(_store)
        except Exception:
            return False

    def cleanup_old_data(self, max_age_hours: int = 24) -> int:
        """Clean up old data - Redis handles this with TTL automatically"""

        def _cleanup():
            # Redis automatically handles expiration with TTL
            # Count keys that would be cleaned up
            keys = self._redis_client.keys(f"{self.key_prefix}*")

            cleaned_count = 0
            for key in keys:
                try:
                    ttl = self._redis_client.ttl(key)
                    if ttl == -1:  # No expiration set, add one
                        self._redis_client.expire(key, max_age_hours * 3600)
                        cleaned_count += 1
                except Exception:
                    continue

            return cleaned_count

        if self._redis_available:
            try:
                return self._execute_with_retry(_cleanup)
            except Exception:
                return 0
        return 0

    def get_health_status(self) -> Dict[str, Any]:
        """Get Redis connection health status"""
        status = {
            "redis_available": self._redis_available,
            "fallback_active": self._file_fallback is not None,
            "redis_url": self.redis_url,
            "redis_db": self.redis_db,
            "connection_timeout": self.connection_timeout,
        }

        if self._redis_available and self._redis_client:
            try:
                # Test connection and get info
                info = self._redis_client.info()
                status.update(
                    {
                        "redis_version": info.get("redis_version", "unknown"),
                        "connected_clients": info.get("connected_clients", 0),
                        "used_memory_human": info.get("used_memory_human", "unknown"),
                        "uptime_in_seconds": info.get("uptime_in_seconds", 0),
                    }
                )

                # Count agentdiff keys
                keys = self._redis_client.keys(f"{self.key_prefix}*")
                status["agentdiff_keys"] = len(keys)

            except Exception as e:
                status["redis_error"] = str(e)

        return status

    def reset_all_data(self):
        """Reset all AgentDiff data in Redis"""

        def _reset():
            keys = self._redis_client.keys(f"{self.key_prefix}*")
            if keys:
                self._redis_client.delete(*keys)
            return len(keys)

        if self._redis_available:
            return self._execute_with_retry(_reset)
        elif self._file_fallback:
            return self._file_fallback.reset_all_data()
        return 0

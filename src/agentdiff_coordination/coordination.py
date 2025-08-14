"""
Core coordination primitive
"""

import threading
from typing import Dict, Optional
from .exceptions import CoordinationTimeoutError


class AgentLock:
    """
    Named resource locks to prevent concurrent access.

    Usage:
        with AgentLock("database"):
            agent1.update_records()  # Only one agent can access at a time

        with AgentLock("api_quota"):
            agent2.make_api_call()  # Prevent quota exhaustion

    Features:
    - Named locks (shared across threads)
    - Automatic cleanup via reference counting
    - Timeout support
    - Testing utilities for cleanup
    """

    # Class-level lock management with reference counting
    _locks: Dict[str, threading.RLock] = {}
    _ref_counts: Dict[str, int] = {}
    _cleanup_lock = threading.RLock()

    def __init__(self, resource_name: str, timeout: Optional[float] = None):
        self.resource_name = resource_name
        self.timeout = timeout
        self._acquired = False

        # Get or create lock with reference counting
        with self._cleanup_lock:
            if resource_name not in self._locks:
                self._locks[resource_name] = threading.RLock()
                self._ref_counts[resource_name] = 0

            self._ref_counts[resource_name] += 1
            self.lock = self._locks[resource_name]

    def __enter__(self):
        """Acquire the named resource lock"""
        if self.timeout:
            acquired = self.lock.acquire(timeout=self.timeout)
            if not acquired:
                raise CoordinationTimeoutError(
                    f"Failed to acquire lock '{self.resource_name}' within {self.timeout}s"
                )
        else:
            self.lock.acquire()

        self._acquired = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release the named resource lock"""
        if self._acquired:
            self.lock.release()
            self._acquired = False

    def __del__(self):
        """Automatic cleanup when AgentLock object is garbage collected"""
        try:
            with self._cleanup_lock:
                if self.resource_name in self._ref_counts:
                    self._ref_counts[self.resource_name] -= 1

                    # Clean up unused locks automatically
                    if self._ref_counts[self.resource_name] <= 0:
                        self._locks.pop(self.resource_name, None)
                        self._ref_counts.pop(self.resource_name, None)
        except Exception:
            # Suppress all exceptions in __del__ to avoid interpreter warnings
            pass

    @classmethod
    def is_locked(cls, resource_name: str) -> bool:
        """Check if a named resource is currently locked"""
        with cls._cleanup_lock:
            if resource_name not in cls._locks:
                return False

            # Try to acquire with timeout=0 (non-blocking)
            lock = cls._locks[resource_name]
            acquired = lock.acquire(blocking=False)
            if acquired:
                lock.release()
                return False
            return True

    @classmethod
    def get_active_locks(cls) -> Dict[str, int]:
        """Get all active locks and their reference counts (for debugging)"""
        with cls._cleanup_lock:
            return cls._ref_counts.copy()

    @classmethod
    def cleanup_unused_locks(cls) -> int:
        """Force cleanup of unused locks (for testing)"""
        cleaned = 0
        with cls._cleanup_lock:
            unused_locks = [
                name for name, count in cls._ref_counts.items() if count <= 0
            ]
            for lock_name in unused_locks:
                cls._locks.pop(lock_name, None)
                cls._ref_counts.pop(lock_name, None)
                cleaned += 1
        return cleaned

    @classmethod
    def force_cleanup_all_locks(cls) -> int:
        """Force cleanup of ALL locks (for testing only!)"""
        with cls._cleanup_lock:
            count = len(cls._locks)
            cls._locks.clear()
            cls._ref_counts.clear()
            return count

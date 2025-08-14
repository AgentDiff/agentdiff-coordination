"""
Persistence interface for AgentDiff coordination system.

Defines the contract that all persistence backends must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class Message:
    """Standard message structure for persistence layer"""

    topic: str
    payload: Any
    timestamp: float
    message_id: str
    sender: Optional[str] = None
    correlation_id: Optional[str] = None
    retry_count: int = 0


class PersistenceBackend(ABC):
    """
    Abstract base class for all persistence backends.

    This ensures consistent behavior across File, Redis, Kafka, PostgreSQL, etc.
    """

    @abstractmethod
    def store_message(self, message: Message) -> bool:
        """
        Store a message for persistence/replay.

        Args:
            message: Message to store

        Returns:
            True if stored successfully, False otherwise
        """
        pass

    @abstractmethod
    def store_dead_letter(self, entry: Dict[str, Any]) -> bool:
        """
        Store a dead letter entry for failed message processing.

        Args:
            entry: Dead letter entry with message, subscriber_id, failure_time, reason

        Returns:
            True if stored successfully, False otherwise
        """
        pass

    @abstractmethod
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the persistence backend.

        Returns:
            Dictionary with health information (connected, latency, etc.)
        """
        pass

    @abstractmethod
    def cleanup_old_data(self, max_age_hours: int = 24) -> int:
        """
        Clean up old data based on age.

        Args:
            max_age_hours: Maximum age of data to keep in hours

        Returns:
            Number of items cleaned up
        """
        pass

    def replay_messages(self, since_timestamp: float = None) -> List[Message]:
        """
        Replay messages since a given timestamp (optional).

        Args:
            since_timestamp: Only return messages newer than this timestamp

        Returns:
            List of messages for replay
        """
        # Default implementation returns empty list (not all backends need replay)
        return []

    def get_stats(self) -> Dict[str, Any]:
        """
        Get backend-specific statistics (optional).

        Returns:
            Dictionary with backend statistics
        """
        return {"backend_type": self.__class__.__name__}


class NullPersistence(PersistenceBackend):
    """No-op persistence for testing or when persistence is disabled"""

    def store_message(self, message: Message) -> bool:
        return True

    def store_dead_letter(self, entry: Dict[str, Any]) -> bool:
        return True

    def get_health_status(self) -> Dict[str, Any]:
        return {
            "backend_type": "null",
            "status": "healthy",
            "persistence_enabled": False,
        }

    def cleanup_old_data(self, max_age_hours: int = 24) -> int:
        return 0

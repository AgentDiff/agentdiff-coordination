"""
File-based persistence backend for AgentDiff coordination system.
"""

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from .persistence_interface import PersistenceBackend, Message


class FilePersistence(PersistenceBackend):
    """File-based persistence backend"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            try:
                import appdirs

                data_dir = appdirs.user_data_dir("agentdiff", "agentdiff")
            except ImportError:
                data_dir = os.path.expanduser("~/.agentdiff")

        self.data_dir = Path(data_dir)
        self.coordination_dir = self.data_dir / "coordination"
        self.session_file = self._get_session_file()
        self._lock = threading.RLock()

        # Ensure directories exist
        self.coordination_dir.mkdir(parents=True, exist_ok=True)

        # Test write permissions
        self._test_write_permissions()

    def _get_session_file(self) -> Path:
        """Generate unique session file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()
        return self.coordination_dir / f"session_{timestamp}_{pid}.log"

    def _test_write_permissions(self):
        """Test if we can write to the directory"""
        try:
            test_file = self.coordination_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
        except (OSError, PermissionError) as e:
            raise RuntimeError(
                f"Cannot write to coordination directory {self.coordination_dir}: {e}"
            )

    def store_message(self, message: Message) -> bool:
        """Store message to file"""
        with self._lock:
            try:
                entry = {
                    "timestamp": message.timestamp,
                    "topic": message.topic,
                    "payload": message.payload,
                    "message_id": message.message_id,
                    "sender": message.sender,
                    "correlation_id": message.correlation_id,
                }

                with open(self.session_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")

                return True
            except Exception:
                return False

    def store_dead_letter(self, entry: Dict[str, Any]) -> bool:
        """Store dead letter entry to persistent file"""
        with self._lock:
            try:
                dead_letter_file = self.coordination_dir / "dead_letters.jsonl"
                with open(dead_letter_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
                return True
            except Exception:
                return False

    def replay_messages(self, since_timestamp: float = None) -> List[Message]:
        """Replay messages from current session file"""
        if not self.session_file.exists():
            return []

        messages = []
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        entry = json.loads(line.strip())

                        if since_timestamp and entry["timestamp"] <= since_timestamp:
                            continue

                        message = Message(
                            topic=entry["topic"],
                            payload=entry["payload"],
                            timestamp=entry["timestamp"],
                            message_id=entry["message_id"],
                            sender=entry.get("sender"),
                            correlation_id=entry.get("correlation_id"),
                        )
                        messages.append(message)

                    except json.JSONDecodeError:
                        continue

        except Exception:
            pass

        return messages

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of file persistence"""
        status = {
            "backend_type": "file",
            "data_dir": str(self.data_dir),
            "session_file": str(self.session_file),
            "persistence_enabled": True,
        }

        try:
            # Check if session file exists and is writable
            if self.session_file.exists():
                status["session_file_size"] = self.session_file.stat().st_size
                status["last_modified"] = self.session_file.stat().st_mtime

            # Test write access
            self._test_write_permissions()
            status["writable"] = True
            status["status"] = "healthy"

        except Exception as e:
            status["writable"] = False
            status["status"] = "unhealthy"
            status["error"] = str(e)

        return status

    def cleanup_old_data(self, max_age_hours: int = 24) -> int:
        """Clean up old session files"""
        cutoff = time.time() - (max_age_hours * 3600)
        cleaned_count = 0

        try:
            for session_file in self.coordination_dir.glob("session_*.log"):
                if session_file.stat().st_mtime < cutoff:
                    session_file.unlink()
                    cleaned_count += 1
        except Exception:
            pass

        return cleaned_count

    def get_stats(self) -> Dict[str, Any]:
        """Get file persistence statistics"""
        stats = super().get_stats()

        try:
            # Count session files
            session_files = list(self.coordination_dir.glob("session_*.log"))
            stats["session_files_count"] = len(session_files)

            # Count dead letter files
            dead_letter_files = list(self.coordination_dir.glob("dead_letters.jsonl"))
            stats["dead_letter_files_count"] = len(dead_letter_files)

            # Current session file size
            if self.session_file.exists():
                stats["current_session_size"] = self.session_file.stat().st_size

        except Exception:
            pass

        return stats

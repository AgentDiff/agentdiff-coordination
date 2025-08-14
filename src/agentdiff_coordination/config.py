"""
AgentDiff Configuration
This module provides the configuration for the AgentDiff coordination library.
It uses environment variables with programmatic overrides to set up the configuration.
The configuration includes settings for persistence backends, logging, and Redis connection.
"""

import os
from dataclasses import dataclass, field, fields
from typing import Optional, Any, Union


AGENTDIFF_COORDINATION_PERSISTENCE_BACKEND = (
    "AGENTDIFF_COORDINATION_PERSISTENCE_BACKEND"
)
AGENTDIFF_COORDINATION_DISABLE_PERSISTENCE = (
    "AGENTDIFF_COORDINATION_DISABLE_PERSISTENCE"
)
AGENTDIFF_COORDINATION_DATA_DIR = "AGENTDIFF_COORDINATION_DATA_DIR"
AGENTDIFF_COORDINATION_REDIS_URL = "AGENTDIFF_COORDINATION_REDIS_URL"
AGENTDIFF_COORDINATION_REDIS_PASSWORD = "AGENTDIFF_COORDINATION_REDIS_PASSWORD"
AGENTDIFF_COORDINATION_REDIS_DB = "AGENTDIFF_COORDINATION_REDIS_DB"
AGENTDIFF_COORDINATION_REDIS_PREFIX = "AGENTDIFF_COORDINATION_REDIS_PREFIX"
AGENTDIFF_COORDINATION_LOG_LEVEL = "AGENTDIFF_COORDINATION_LOG_LEVEL"
AGENTDIFF_COORDINATION_LOG_FILE = "AGENTDIFF_COORDINATION_LOG_FILE"
AGENTDIFF_COORDINATION_LOG_JSON = "AGENTDIFF_COORDINATION_LOG_JSON"
AGENTDIFF_COORDINATION_LOG_CONSOLE = "AGENTDIFF_COORDINATION_LOG_CONSOLE"


DEFAULT_AGENTDIFF_COORDINATION_PERSISTENCE_BACKEND = "file"
DEFAULT_AGENTDIFF_COORDINATION_DISABLE_PERSISTENCE = False
DEFAULT_AGENTDIFF_COORDINATION_DATA_DIR = os.path.join(
    os.path.expanduser("~"), ".agentdiff", "coordination"
)
DEFAULT_AGENTDIFF_COORDINATION_REDIS_URL = "redis://localhost:6379"
DEFAULT_AGENTDIFF_COORDINATION_REDIS_PASSWORD = None
DEFAULT_AGENTDIFF_COORDINATION_REDIS_DB = 0
DEFAULT_AGENTDIFF_COORDINATION_REDIS_PREFIX = "agentdiff:"
DEFAULT_AGENTDIFF_COORDINATION_LOG_LEVEL = "INFO"
DEFAULT_AGENTDIFF_COORDINATION_LOG_FILE = None
DEFAULT_AGENTDIFF_COORDINATION_LOG_JSON = False
DEFAULT_AGENTDIFF_COORDINATION_LOG_CONSOLE = True


@dataclass(frozen=True)
class AgentDiffCoordinationConfig:
    """
    Configuration for AgentDiff coordination library.

    Uses environment variables with programmatic overrides:
    - Explicit parameters take highest priority
    - Environment variables take medium priority
    - Default values take lowest priority

    Example:
        # Environment-based config
        config = AgentDiffConfig()

        # Programmatic overrides
        config = AgentDiffConfig(
            persistence_backend="redis",
            log_level="DEBUG",
            redis_url="redis://prod:6379"
        )
    """

    persistence_backend: str = field(
        default=None,
        metadata={
            "env_var": AGENTDIFF_COORDINATION_PERSISTENCE_BACKEND,
            "default_value": DEFAULT_AGENTDIFF_COORDINATION_PERSISTENCE_BACKEND,
            "description": "AgentDiff persistence backend type: 'file', 'redis', or 'none'",
        },
    )
    disable_persistence: bool = field(
        default=None,
        metadata={
            "env_var": AGENTDIFF_COORDINATION_DISABLE_PERSISTENCE,
            "default_value": DEFAULT_AGENTDIFF_COORDINATION_DISABLE_PERSISTENCE,
            "description": "Disable persistence completely",
        },
    )
    data_dir: str = field(
        default=None,
        metadata={
            "env_var": AGENTDIFF_COORDINATION_DATA_DIR,
            "default_value": DEFAULT_AGENTDIFF_COORDINATION_DATA_DIR,
            "description": "Custom data directory path for persistence",
        },
    )
    redis_url: str = field(
        default=None,
        metadata={
            "env_var": AGENTDIFF_COORDINATION_REDIS_URL,
            "default_value": DEFAULT_AGENTDIFF_COORDINATION_REDIS_URL,
            "description": "Redis connection URL",
        },
    )

    redis_password: str = field(
        default=None,
        metadata={
            "env_var": AGENTDIFF_COORDINATION_REDIS_PASSWORD,
            "default_value": DEFAULT_AGENTDIFF_COORDINATION_REDIS_PASSWORD,
            "description": "Redis authentication password",
        },
    )

    redis_db: int = field(
        default=None,
        metadata={
            "env_var": AGENTDIFF_COORDINATION_REDIS_DB,
            "default_value": 0,
            "description": "Redis database number",
        },
    )

    redis_prefix: str = field(
        default=None,
        metadata={
            "env_var": AGENTDIFF_COORDINATION_REDIS_PREFIX,
            "default_value": DEFAULT_AGENTDIFF_COORDINATION_REDIS_PREFIX,
            "description": "Redis key prefix for namespacing",
        },
    )

    log_level: str = field(
        default=None,
        metadata={
            "env_var": AGENTDIFF_COORDINATION_LOG_LEVEL,
            "default_value": DEFAULT_AGENTDIFF_COORDINATION_LOG_LEVEL,
            "description": "Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        },
    )

    log_file: Optional[str] = field(
        default=None,
        metadata={
            "env_var": AGENTDIFF_COORDINATION_LOG_FILE,
            "default_value": DEFAULT_AGENTDIFF_COORDINATION_LOG_FILE,
            "description": "File path for logging output",
        },
    )

    log_json: bool = field(
        default=None,
        metadata={
            "env_var": AGENTDIFF_COORDINATION_LOG_JSON,
            "default_value": DEFAULT_AGENTDIFF_COORDINATION_LOG_JSON,
            "description": "Enable JSON formatted logging",
        },
    )

    log_console: bool = field(
        default=None,
        metadata={
            "env_var": AGENTDIFF_COORDINATION_LOG_CONSOLE,
            "default_value": DEFAULT_AGENTDIFF_COORDINATION_LOG_CONSOLE,
            "description": "Enable console logging output",
        },
    )

    def __post_init__(self):
        """
        Resolve environment variables and defaults after initialization.
        Implements the priority system: explicit > environment > default
        """
        for field_info in fields(self):
            current_value = getattr(self, field_info.name)

            if current_value is None:  # Not explicitly set
                metadata = field_info.metadata
                env_var = metadata["env_var"]
                default_value = metadata["default_value"]

                # Try environment variable first
                if env_value := os.getenv(env_var):
                    parsed_value = self._parse_env_value(env_value, field_info.type)
                    object.__setattr__(self, field_info.name, parsed_value)
                else:
                    # Fall back to default value
                    object.__setattr__(self, field_info.name, default_value)

        # Validate final configuration
        self._validate()

    def _parse_env_value(self, value: str, field_type: type) -> Any:
        """
        Parse environment variable string to correct Python type.
        Handles Optional types and common conversions.
        """
        # Handle Optional types (e.g., Optional[bool] -> bool)
        if hasattr(field_type, "__origin__") and field_type.__origin__ is Union:
            # Get the non-None type from Optional[T]
            field_type = next(t for t in field_type.__args__ if t is not type(None))

        # Type-specific parsing
        if field_type is bool:
            return value.lower() in ("true", "1", "yes", "on", "enabled")
        elif field_type is int:
            return int(value)
        elif field_type is float:
            return float(value)
        else:
            return value  # Keep as string

    def _validate(self):
        """Validate configuration values after parsing"""
        # Persistence backend validation
        if self.persistence_backend not in ["file", "redis", "none"]:
            raise ValueError(
                f"Invalid persistence backend: {self.persistence_backend}. "
                "Must be 'file', 'redis', or 'none'."
            )

        if self.disable_persistence and self.persistence_backend != "none":
            raise ValueError(
                "Cannot disable persistence while using a persistence backend."
            )

        # Log level validation
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"Invalid log level: {self.log_level}. Must be one of {valid_log_levels}"
            )

        # Redis validations (when using Redis backend)
        if self.persistence_backend == "redis":
            # Enhanced Redis URL validation
            if not (
                self.redis_url.startswith("redis://")
                or self.redis_url.startswith("rediss://")
            ):
                raise ValueError(
                    "Redis URL must start with 'redis://' or 'rediss://' (SSL)"
                )

            # Basic URL structure check
            try:
                from urllib.parse import urlparse

                parsed = urlparse(self.redis_url)
                if not parsed.hostname:
                    raise ValueError("Redis URL must include hostname")
            except Exception as e:
                raise ValueError(f"Invalid Redis URL format: {e}")

            # Redis database range validation
            if not (0 <= self.redis_db <= 15):
                raise ValueError(f"Redis database must be 0-15, got: {self.redis_db}")

        # Redis prefix validation
        if not self.redis_prefix or not isinstance(self.redis_prefix, str):
            raise ValueError("Redis prefix must be a non-empty string")
        if len(self.redis_prefix) > 50:
            raise ValueError("Redis prefix too long (max 50 characters)")

        # Data directory validation (for file backend)
        if self.persistence_backend == "file":
            try:
                os.makedirs(self.data_dir, exist_ok=True)
                # Test write permissions
                test_file = os.path.join(self.data_dir, ".write_test")
                with open(test_file, "w") as f:
                    f.write("test")
                os.unlink(test_file)
            except (OSError, PermissionError) as e:
                raise ValueError(f"Cannot write to data directory {self.data_dir}: {e}")

        # Log file directory validation (if specified)
        if self.log_file:
            log_dir = os.path.dirname(os.path.abspath(self.log_file))
            if not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir, exist_ok=True)
                except (OSError, PermissionError) as e:
                    raise ValueError(f"Cannot create log directory {log_dir}: {e}")

    def __repr__(self):
        """Professional string representation for debugging"""
        return (
            f"AgentDiffCoordinationConfig("
            f"persistence_backend='{self.persistence_backend}', "
            f"disable_persistence={self.disable_persistence}, "
            f"redis_url='{self.redis_url}', "
            f"redis_db={self.redis_db}, "
            f"log_level='{self.log_level}', "
            f"log_json={self.log_json})"
        )

    def __str__(self):
        """Human-readable string representation"""
        redis_status = (
            f"redis://.../db{self.redis_db}"
            if self.persistence_backend == "redis"
            else "N/A"
        )
        return (
            f"AgentDiff Coordination Config: "
            f"backend={self.persistence_backend}, "
            f"redis={redis_status}, "
            f"log_level={self.log_level}"
        )


# Global config instance
config = AgentDiffCoordinationConfig()

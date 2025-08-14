"""
AgentDiff Coordination - Lightweight coordination primitives for AI agents

Prevent race conditions and concurrency bugs in multi-agent systems.
Framework-agnostic, thread-safe, and MIT licensed.
"""

__version__ = "0.1.0"
__author__ = "AgentDiff Team"


# Core Agent Coordination API (only 4 essential functions)
from .decorators import coordinate, when, emit
from .pubsub.pubsub_broker import configure_broker

# Essential exceptions for error handling
from .exceptions import CoordinationError, CoordinationTimeoutError

# Hide internal modules from public API
import sys

_module = sys.modules[__name__]
for _name in [
    "decorators",
    "pubsub",
    "exceptions",
    "coordination",
    "logging",
]:
    if hasattr(_module, _name):
        delattr(_module, _name)
del _module, _name, sys

# Clean API exports - only the essentials
__all__ = [
    # Core coordination API (4 functions users actually need)
    "coordinate",  # @coordinate decorator for agent functions
    "when",  # @when decorator for event handlers
    "emit",  # emit() function for sending events
    "configure_broker",  # configure_broker() for production setup
    # Essential error handling
    "CoordinationError",
    "CoordinationTimeoutError",
]

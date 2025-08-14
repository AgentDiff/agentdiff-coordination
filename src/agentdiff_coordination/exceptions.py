"""
Exception classes for AgentDiff Coordination
"""


class CoordinationError(Exception):
    """Base exception for coordination-related errors"""

    pass


class CoordinationTimeoutError(CoordinationError):
    """Raised when coordination operations timeout"""

    pass

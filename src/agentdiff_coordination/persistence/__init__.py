"""
Persistence Backends

Internal persistence system for AgentDiff coordination.
Provides pluggable storage backends for coordination data.

Available backends:
- FilePersistence: Local file-based storage
- RedisPersistence: Redis-based storage with fallback
"""

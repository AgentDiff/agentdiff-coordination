# Configuration Guide

Production configuration and deployment guide for AgentDiff Coordination.

## Environment Variables

All configuration is done through environment variables following the `AGENTDIFF_COORDINATION_*` naming convention.

### Persistence Backend

```bash
# Backend selection  
export AGENTDIFF_COORDINATION_PERSISTENCE_BACKEND=redis  # redis or file

# Redis configuration (if using Redis backend)
export AGENTDIFF_COORDINATION_REDIS_URL=redis://localhost:6379
export AGENTDIFF_COORDINATION_REDIS_PASSWORD=your-secure-password
export AGENTDIFF_COORDINATION_REDIS_DB=0
export AGENTDIFF_COORDINATION_REDIS_PREFIX=agentdiff:

# File backend configuration (if using file backend)
export AGENTDIFF_COORDINATION_DATA_DIR=/var/lib/agentdiff

# Disable persistence entirely (for testing - operates in-memory only)
export AGENTDIFF_COORDINATION_DISABLE_PERSISTENCE=true
```

### Logging Configuration

```bash
# Log level
export AGENTDIFF_COORDINATION_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# Log output
export AGENTDIFF_COORDINATION_LOG_FILE=/var/log/agentdiff/coordination.log
export AGENTDIFF_COORDINATION_LOG_CONSOLE=true
export AGENTDIFF_COORDINATION_LOG_JSON=true  # Structured logging for production
```

## Backend Selection Guide

### Development: File Backend

Best for local development and testing.

```bash
export AGENTDIFF_COORDINATION_PERSISTENCE_BACKEND=file
export AGENTDIFF_COORDINATION_DATA_DIR=/tmp/agentdiff
export AGENTDIFF_COORDINATION_LOG_LEVEL=DEBUG
export AGENTDIFF_COORDINATION_LOG_CONSOLE=true
```

**Pros:**

- No external dependencies
- Simple setup
- Good for development

**Cons:**

- Not suitable for distributed systems
- Limited performance
- No built-in cleanup

### Production: Redis Backend

Recommended for production deployments.

```bash
export AGENTDIFF_COORDINATION_PERSISTENCE_BACKEND=redis
export AGENTDIFF_COORDINATION_REDIS_URL=redis://prod-redis:6379
export AGENTDIFF_COORDINATION_REDIS_PASSWORD=secure-production-password
export AGENTDIFF_COORDINATION_REDIS_DB=1
export AGENTDIFF_COORDINATION_LOG_LEVEL=INFO
export AGENTDIFF_COORDINATION_LOG_JSON=true
export AGENTDIFF_COORDINATION_LOG_FILE=/var/log/agentdiff/coordination.log
```

**Pros:**

- High performance
- Distributed coordination
- Built-in persistence
- Automatic cleanup

**Cons:**

- Requires Redis server
- Additional operational complexity

## Programmatic Configuration

### Basic Setup

```python
from agentdiff_coordination import configure_broker

# Redis for production
configure_broker("redis",
    redis_url="redis://prod-redis:6379",
    redis_password="secure-password",
    redis_db=1,
    key_prefix="myapp:",
    fallback_to_file=True  # Fallback if Redis unavailable
)

# [Optiona] File configuration for development
configure_broker("file",
    dir="/var/lib/agentdiff"
)

```

### Advanced Redis Configuration

```python
configure_broker("redis",
    redis_url="redis://prod-redis:6379",
    redis_password="secure-password",
    redis_db=2,
    key_prefix="agentdiff:production:",

    # Connection pool settings
    max_connections=20,
    retry_on_timeout=True,
    socket_timeout=30,
    socket_connect_timeout=30,

    # Fallback options
    fallback_to_file=True,
    fallback_dir="/tmp/agentdiff-fallback"
)
```

### Reading Current Configuration

```python
from agentdiff_coordination.config import config

print(config)
```

# API Reference

Simple reference for AgentDiff Coordination - just the essentials.

## Core Decorators

### `@coordinate(name, lock_name=None)`

Main coordination decorator that provides resource locking and automatic lifecycle events.

**Parameters:**

- `name` (str): Agent identifier used for logging and events
- `lock_name` (str, optional): Resource lock name to prevent conflicts

**Automatic Events Emitted:**

- `{name}_started` - When agent function begins
- `{name}_complete` - When agent function succeeds
- `{name}_failed` - When agent function raises exception

**Example:**

```python
@coordinate("data_processor", lock_name="database")
def process_data(data):
    # Only one agent can access database at a time
    # Events: data_processor_started, data_processor_complete/failed
    return transform(data)
```

**Event Data Structure:**

```python
# {name}_started event
{
    "args": (arg1, arg2),
    "kwargs": {"key": "value"},
    "timestamp": 1234567890.123
}

# {name}_complete event
{
    "result": return_value,
    "timestamp": 1234567890.123,
    "duration": 1.234
}

# {name}_failed event
{
    "error": "Exception message",
    "timestamp": 1234567890.123,
    "duration": 1.234
}
```

### `@when(event_name)`

Decorator that registers event handlers.

```python
@when("researcher_complete")
def handle_research_done(event_data):
    result = event_data['result']
    print(f"Research done: {result}")
```

**Parameters:**

- `event_name` (str): Event name to listen for

**Handler receives:** `event_data` dict with event payload

**Example:**

```python
@when("data_processor_complete")
def handle_data_ready(event_data):
    result = event_data['result']
    duration = event_data['duration']
    print(f"Processing took {duration:.2f}s")
```

---

## Core Functions

### `emit(event_name, data=None, sender=None)`

Function to trigger custom events.

```python
emit("data_ready", {"dataset": processed_data})
```

**Parameters:**

- `event_name` (str): Event name to emit
- `data` (any, optional): Event data payload
- `sender` (str, optional): Sender identification

**Returns:** Message ID string

### `configure_broker(backend, [**config])`

Configure event persistence (only needed for production).

```python
from agentdiff_coordination import configure_broker

# For development (default)
configure_broker("inmemory")

# For production
configure_broker("redis")
configure_broker("file")
```

**Parameters:**

- `backend` (str): Backend type - "file", "redis", or "none" (disable persistence)
- `**config`: Backend-specific configuration

#### Backend Options

**File Backend**

File-based persistence

```python
configure_broker("file",
    dir="/var/lib/agentdiff"  # Data directory
)
```

**Redis Backend**

Redis persistence for production

```python
configure_broker("redis",
    redis_url="redis://localhost:6379",
    redis_password="password",
    redis_db=0,
    key_prefix="agentdiff:",
    fallback_to_file=True
)
```

**Disable Persistence**

For testing - events stored in memory only, no persistence

```python
# Disable persistence via environment variable (recommended)
import os
os.environ["AGENTDIFF_COORDINATION_DISABLE_PERSISTENCE"] = "true"

# Or disable via configure_broker
configure_broker("none")  # No persistence - in-memory only
```

---

That's it! For 90% of use cases, you only need `@coordinate`, `@when`, and `emit()`.

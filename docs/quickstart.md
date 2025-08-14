# Quickstart Guide

Get up and running with AgentDiff Coordination in 5 minutes.

## Installation

```bash
pip install agentdiff-coordination
```

## Basic Example

```python
from agentdiff_coordination import coordinate, when, emit
import time

@coordinate("worker") #agent_name is "worker"
def do_work(task_id):
    """A simple agent that does work"""
    print(f"Starting work on task {task_id}")
    time.sleep(2)  # Simulate work
    result = f"Task {task_id} completed"
    return result

@when("worker_complete") #auto generated event on task completion <agent_name>_complete
def handle_work_done(event_data):
    """Handle when work is finished"""
    print(f"Work finished: {event_data['result']}")

@when("worker_failed") #auto generated event on task failure <agent_name>_failed
def handle_work_error(event_data):
    """Handle when work fails"""
    print(f"Work failed: {event_data['error']}")

# Run the agent
result = do_work("task_001")
```

**Output:**

```
Starting work on task task_001
Work finished: Task task_001 completed
```

## Resource Protection

Prevent multiple agents from conflicting over shared resources:

```python
import openai
from agentdiff_coordination import coordinate

# Protect API calls with locks
@coordinate("llm_agent", lock_name="openai_api")
def call_llm(prompt):
    """Only one agent can call OpenAI at a time"""
    response = openai.responses.create(
        model="gpt-3.5-turbo",
        input=prompt
    )
    return response.choices[0].message.content

# Multiple agents can call this safely - they'll queue automatically
result1 = call_llm("What is AI?")
result2 = call_llm("Explain machine learning")
```

## Event-Driven Coordination

Chain agents together with events:

```python
from agentdiff_coordination import coordinate, when, emit

@coordinate("data_fetcher") #agent_name is data_fetcher
def fetch_data():
    """Fetch raw data"""
    data = ["item1", "item2", "item3"]
    return data

@when("data_fetcher_complete") #auto generated event <agent_name>_complete
def process_data(event_data):
    """Process data when fetching completes"""
    raw_data = event_data['result']
    processed = [item.upper() for item in raw_data]

    # Trigger next step
    emit("data_processed", {"processed_data": processed}) #emit a custom event "data_processed"

@when("data_processed")
def save_data(event_data):
    """Save processed data"""
    data = event_data['processed_data']
    print(f"Saving: {data}")

# Start the pipeline
fetch_data()
```

## Production Configuration

For production deployment, see the **[Configuration Guide](configuration.md)** for complete setup instructions including Redis backend, logging, and environment variables.

## Error Handling

```python
from agentdiff_coordination import coordinate, CoordinationTimeoutError

@coordinate("risky_operation", lock_name="critical_resource")
def risky_work():
    """Work that might fail"""
    raise Exception("Something went wrong!")

try:
    risky_work()
except Exception as e:
    print(f"Work failed: {e}")
    # The @coordinate decorator automatically emits risky_operation_failed event
```

## Testing Your Setup

```python
from agentdiff_coordination import coordinate, when, emit
import threading
import time

def test_coordination():
    """Test that coordination is working"""
    results = []

    @coordinate("test_agent")
    def test_work(value):
        time.sleep(0.1)
        return f"processed_{value}"

    @when("test_agent_complete")
    def collect_result(event_data):
        results.append(event_data['result'])

    # Run multiple agents in parallel
    threads = []
    for i in range(3):
        t = threading.Thread(target=test_work, args=(i,))
        threads.append(t)
        t.start()

    # Wait for completion
    for t in threads:
        t.join()

    time.sleep(0.5)  # Allow events to process
    print(f"Results: {results}")

if __name__ == "__main__":
    test_coordination()
```

## Next Steps

- **[API Reference](api-reference.md)** - Complete API documentation
- **[Working Examples](../examples/)** - Real-world usage patterns and integrations
- **[Configuration](configuration.md)** - Production deployment guide

## Common Issues

**Q: Events not firing?**
A: Make sure you're not blocking the main thread. Events are processed asynchronously.

**Q: Locks not working?**
A: Ensure you're using the same `lock_name` across all agents that should be synchronized.

**Q: Performance slow?**
A: Consider using Redis backend for production - file backend is meant for development.

**Q: Import errors?**
A: Make sure you installed with: `pip install agentdiff-coordination`

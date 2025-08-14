# AgentDiff Coordination

AgentDiff is a lightweight coordination library that prevents common concurrency issues in multi-agent systems - such as agents starting before dependencies complete, multiple agents writing to shared resources, or concurrent API calls exceeding rate limits.

Simply add `@coordinate` decorators for resource locks and `@when` for event-driven chaining. AgentDiff integrates with existing agent frameworks like LangChain, CrewAI, or pure Python implementations.

Provides coordination primitives without requiring framework migration or architectural changes.

[![PyPI version](https://badge.fury.io/py/agentdiff-coordination.svg)](https://badge.fury.io/py/agentdiff-coordination)
[![Python Support](https://img.shields.io/pypi/pyversions/agentdiff-coordination.svg)](https://pypi.org/project/agentdiff-coordination/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What AgentDiff Coordination Solves

- **Race conditions** between agents accessing shared resources.
- **Corrupted state** when multiple agents write to the same keys.
- **API rate limit chaos** from concurrent LLM calls.
- **"Two nodes writing to same key"** bugs that require extensive debugging.
- **Framework complexity** that gets in the way of actually building agents.

## Core Features

- **`@coordinate`** - Resource locks + automatic lifecycle events.
- **`@when`** - Event-driven agent chaining (no manual orchestration).
- **`emit()`** - Custom events for complex workflows.
- **Zero Configuration** - Works immediately, configure only what you need.
- **Framework Agnostic** - Works with any agent framework or pure Python.

## Use Cases: Concurrency Issues and Race Conditions

### **Concurrent State Updates**

```python
# Before: Race conditions in shared state
def process_customer_data():
    customer_state["status"] = "processing"  # Race condition
    result = process_data()
    customer_state["result"] = result       # Overwrites other agent

def update_customer_profile():
    customer_state["status"] = "updating"   # Conflicts with processor
    customer_state["profile"] = new_profile # State corruption

# After: Resource locks prevent conflicts
@coordinate("data_processor", lock_name="customer_123")
def process_customer_data():
    customer_state["status"] = "processing"  # Exclusive access
    result = process_data()
    customer_state["result"] = result        # Safe update

@coordinate("profile_updater", lock_name="customer_123")
def update_customer_profile():
    customer_state["status"] = "updating"    # Waits for processor
    customer_state["profile"] = new_profile  # No conflicts
```

### **API Rate Limit Management**

```python
# Before: Multiple agents hitting APIs simultaneously
def research_agent():
    response = openai.chat.completions.create(...)  #  Rate limited

def analysis_agent():
    response = openai.chat.completions.create(...)  #  Rate limited

def summary_agent():
    response = openai.chat.completions.create(...)  #  Rate limited

# Running in parallel creates debugging challenges
threading.Thread(target=research_agent).start()
threading.Thread(target=analysis_agent).start()
threading.Thread(target=summary_agent).start()

# After: Resource locks queue API calls safely
@coordinate("researcher", lock_name="openai_api")
def research_agent():
    response = openai.chat.completions.create(...)  #  Queued safely

@coordinate("analyzer", lock_name="openai_api")
def analysis_agent():
    response = openai.chat.completions.create(...)  #  Waits for researcher

@coordinate("summarizer", lock_name="openai_api")
def summary_agent():
    response = openai.chat.completions.create(...)  #  Waits for analyzer
```

### **Manual Orchestration Complexity**

```python
# Before: Complex manual coordination
def run_workflow():
    research_result = research_agent()
    if research_result:
        analysis_result = analysis_agent(research_result)
        if analysis_result:
            summary_result = summary_agent(analysis_result)
            if summary_result:
                final_report = editor_agent(summary_result)
    # Error handling, retries, parallel flows increase complexity

# After: Event-driven coordination
@coordinate("researcher")
def research_agent():
    return research_data

@when("researcher_complete")
def start_analysis(event_data):
    analysis_agent(event_data['result'])  #  Auto-triggered

@when("analyzer_complete")
def start_summary(event_data):
    summary_agent(event_data['result'])   #  Auto-chained

# Just start the workflow - coordination happens automatically
research_agent()  # Everything else flows automatically
```

## Scope & Guarantees

**Single-Process Coordination**

- Thread-safe coordination within a single Python process.
- Resource locks prevent race conditions between agents in the same process.
- Event-driven workflow orchestration between functions.
- Optional Redis persistence for event storage and monitoring.

**Consistency Model:**

- **Locks**: Cooperative threading locks with optional timeout.
- **Events**: Best-effort delivery within process, optional Redis persistence.
- **Ordering**: Event handlers execute in registration order.
- **Failure**: Agent failures emit error events, no automatic retries.

**When to Use:**

- Single-process agent workflows.
- Development and prototyping of multi-agent systems.
- Thread-safe coordination without external infrastructure.
- Preventing API rate limits and resource conflicts.

**When NOT to Use:**

- **Distributed systems** requiring cross-pod/cross-machine coordination.
- **Mission-critical workflows** needing guaranteed delivery.
- **Long-running workflows** spanning hours/days (use Temporal, Prefect).
- **Strict consistency** requirements (use proper distributed locks).

**Redis Mode Limitations:**

- Persistence for monitoring only, not distributed coordination.
- No cross-process lock sharing.
- No guaranteed event delivery across process restarts.

**Security Considerations:**

- Event payloads are not validated - implement size limits and schema validation as needed.
- Resource locks are cooperative - not suitable for untrusted environments.
- Redis persistence stores events in plain text.

## Installation & Requirements

**Python Support**: 3.9+ (tested on 3.9, 3.10, 3.11, 3.12)

```bash
pip install agentdiff-coordination
```

**Quick Start:**

```python
from agentdiff_coordination import coordinate, when, emit
```

## Documentation

- **[Quick Start Guide](docs/quickstart.md)** - Get up and running in 5 minutes.
- **[API Reference](docs/api-reference.md)** - Complete function documentation.
- **[Use cases](docs/use-cases.md)** - Example use cases.
- **[Configuration Guide](docs/configuration.md)** - Environment variables and settings.
- **[Examples](examples/)** - Example agent coordination patterns.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## About AgentDiff

AgentDiff provides practical tools for AI developers working with multi-agent systems. This coordination library addresses common concurrency challenges encountered in production agent workflows.

- **GitHub**: [https://github.com/AgentDiff](https://github.com/AgentDiff)
- **Issues**: [Report bugs and request features](https://github.com/AgentDiff/agentdiff-coordination/issues)
- **Community**: Share coordination patterns and production experiences

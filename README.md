# AgentDiff Coordination

**Stop debugging concurrency issues in your agent frameworks. AgentDiff prevents race conditions without the complexity.**

[![PyPI version](https://badge.fury.io/py/agentdiff-coordination.svg)](https://badge.fury.io/py/agentdiff-coordination)
[![Python Support](https://img.shields.io/pypi/pyversions/agentdiff-coordination.svg)](https://pypi.org/project/agentdiff-coordination/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Tired of Framework Debugging Hell?

**Sound familiar?**

- Spent days debugging "two nodes writing to same key" errors
- Fought race conditions in fan-out workflows that mysteriously break
- Gave up on complex frameworks and built coordination from scratch
- Hit API rate limits when multiple agents run simultaneously
- Lost weeks to concurrency bugs instead of building features

**You shouldn't spend more time debugging frameworks than building agents.**

## What AgentDiff Coordination Solves

The exact problems developers face with popular agent frameworks and custom agent systems:

- **Race conditions** between agents accessing shared resources
- **Corrupted state** when multiple agents write to the same keys  
- **API rate limit chaos** from concurrent LLM calls
- **"Two nodes writing to same key"** bugs that waste days of debugging
- **Framework complexity** that gets in the way of actually building agents

## Simple Solution: 3 Lines of Code

**Instead of fighting framework complexity, just add coordination where you need it:**

```bash
pip install agentdiff-coordination
```

**Fix the "two nodes writing to same key" problem:**

```python
from agentdiff_coordination import coordinate, when, emit

# Prevent race conditions with resource locks
@coordinate("data_processor", lock_name="customer_database")
def process_customer_data(customer_id, data):
    # Only one agent can access this resource at a time
    return database.update_customer(customer_id, data)

# Prevent API rate limits with resource locks  
@coordinate("researcher", lock_name="openai_api")
def research_agent(topic):
    # Only one agent can call OpenAI at a time
    client = openai.OpenAI()
    return client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": f"Research: {topic}"}]
    )

# Event-driven coordination (no manual orchestration)
@when("researcher_complete")  # Auto-triggered when research_agent() finishes
def handle_research_done(event_data):
    result = event_data['result']
    analysis_agent(result)  # Chain agents automatically

# Works with your existing code - no framework lock-in
research_agent("AI safety")
```

## Why Choose AgentDiff Over Framework Wrestling?

### **✅ Lightweight vs. Heavyweight**
- **AgentDiff**: 3 decorators, works with your existing code
- **Full Frameworks**: Months of learning, complex abstractions, debugging hell

### **✅ Surgical Solution vs. Full Rewrite**  
- **AgentDiff**: Add coordination exactly where you need it
- **Full Frameworks**: Rewrite everything to fit their patterns

### **✅ Production-Ready vs. Experimental**
- **AgentDiff**: Solves specific, well-understood concurrency problems  
- **Full Frameworks**: "Early stages," frequent breaking changes

### **✅ No Lock-In vs. Framework Prison**
- **AgentDiff**: Remove decorators and your code still works
- **Full Frameworks**: Vendor lock-in, hard to migrate away

## Core Features

- **`@coordinate`** - Resource locks + automatic lifecycle events  
- **`@when`** - Event-driven agent chaining (no manual orchestration)
- **`emit()`** - Custom events for complex workflows
- **Zero Configuration** - Works immediately, configure only what you need
- **Framework Agnostic** - Works with any agent framework or pure Python

## Real-World Problem: Concurrent Agent Chaos

**Before AgentDiff (The Reddit Pain):**
```python
# Multiple agents hitting OpenAI simultaneously = rate limit errors
def research_agent(topic):
    client = openai.OpenAI()
    response = client.chat.completions.create(...)  # 💥 Rate limited
    
def analysis_agent(data):  
    client = openai.OpenAI()
    response = client.chat.completions.create(...)  # 💥 Rate limited

# Running these in parallel = debugging hell
threading.Thread(target=research_agent, args=("AI",)).start()
threading.Thread(target=analysis_agent, args=("data",)).start()
```

**After AgentDiff (Problem Solved):**

```python
from agentdiff_coordination import coordinate, when, emit
import openai
import anthropic

# Agent 1: Research with OpenAI (protected by API lock)
@coordinate("researcher", lock_name="openai_api")
def research_agent(topic):
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Research: {topic}"}]
    )
    return response

# Agent 2: Analysis with Anthropic (protected by different lock)
@coordinate("analyzer", lock_name="anthropic_api")
def analysis_agent(research_data):
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=1024,
        messages=[{"role": "user", "content": f"Analyze: {research_data}"}]
    )
    return response.content[0].text

# Agent 3: Final summary (no API calls, no lock needed)
@coordinate("summarizer")
def summary_agent(analysis_result):
    return f"Summary: {analysis_result[:200]}..."

# Event-driven coordination
@when("researcher_complete")
def handle_research_done(event_data):
    research_result = event_data['result']
    analysis_agent(research_result)  # Trigger next agent

@when("analyzer_complete")
def handle_analysis_done(event_data):
    analysis_result = event_data['result']
    summary_agent(analysis_result)    # Trigger final agent

@when("summarizer_complete")
def handle_summary_done(event_data):
    final_summary = event_data['result']
    print(f" Workflow complete: {final_summary}")

# Start the agent workflow
if __name__ == "__main__":
    research_agent("Impact of AI on software development")
```

## Common Agent Coordination Problems AgentDiff Fixes

### **Concurrent State Updates**
```python
# Before: Race conditions in shared state
def process_customer_data():
    customer_state["status"] = "processing"  # 💥 Race condition
    result = process_data()
    customer_state["result"] = result       # 💥 Overwrites other agent

def update_customer_profile():  
    customer_state["status"] = "updating"   # 💥 Conflicts with processor
    customer_state["profile"] = new_profile # 💥 State corruption

# After: Resource locks prevent conflicts
@coordinate("data_processor", lock_name="customer_123")
def process_customer_data():
    customer_state["status"] = "processing"  # ✅ Exclusive access
    result = process_data()
    customer_state["result"] = result        # ✅ Safe update

@coordinate("profile_updater", lock_name="customer_123")  
def update_customer_profile():
    customer_state["status"] = "updating"    # ✅ Waits for processor
    customer_state["profile"] = new_profile  # ✅ No conflicts
```

### **API Rate Limit Chaos**  
```python
# Before: Multiple agents hitting APIs simultaneously
def research_agent():
    response = openai.chat.completions.create(...)  # 💥 Rate limited

def analysis_agent():
    response = openai.chat.completions.create(...)  # 💥 Rate limited

def summary_agent():
    response = openai.chat.completions.create(...)  # 💥 Rate limited

# Run in parallel = debugging nightmare
threading.Thread(target=research_agent).start()
threading.Thread(target=analysis_agent).start()
threading.Thread(target=summary_agent).start()

# After: Resource locks queue API calls safely
@coordinate("researcher", lock_name="openai_api")
def research_agent():
    response = openai.chat.completions.create(...)  # ✅ Queued safely

@coordinate("analyzer", lock_name="openai_api")
def analysis_agent():
    response = openai.chat.completions.create(...)  # ✅ Waits for researcher

@coordinate("summarizer", lock_name="openai_api")
def summary_agent():
    response = openai.chat.completions.create(...)  # ✅ Waits for analyzer
```

### **Manual Orchestration Nightmare**
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
    # 💥 Error handling, retries, parallel flows = complexity explosion

# After: Event-driven coordination  
@coordinate("researcher")
def research_agent():
    return research_data

@when("researcher_complete")  
def start_analysis(event_data):
    analysis_agent(event_data['result'])  # ✅ Auto-triggered

@when("analyzer_complete")
def start_summary(event_data):
    summary_agent(event_data['result'])   # ✅ Auto-chained

# Just start the workflow - coordination happens automatically
research_agent()  # Everything else flows automatically
```

## Example Use Cases & Solutions

### Booking agent confirms a room while Research agent is still comparing options.

**Problem:** Race condition in travel planning workflow  
**Solution:** Use event-driven coordination to ensure proper sequencing

```python
@coordinate("hotel_researcher")
def research_hotels(destination, dates):
    hotels = search_hotels(destination, dates)
    best_hotel = analyze_options(hotels)
    return best_hotel  # @coordinate automatically puts this in event_data['result']

@when("hotel_researcher_complete")  # Auto-triggered when research_hotels() completes
def start_booking(event_data):
    selected_hotel = event_data['result']  # Gets the return value from research_hotels()
    booking_agent(selected_hotel)

# Option 1: Without @coordinate (minimal - just does the work)
def booking_agent(hotel):
    return book_hotel(hotel)

# Option 2: With @coordinate (adds monitoring + events for booking step)
# @coordinate("hotel_booker")
# def booking_agent(hotel):
#     return book_hotel(hotel)  # Also emits hotel_booker_started/complete events
```

### Data analysis started before data collection finished

**Problem:** Analyzer working with incomplete data  
**Solution:** Event-driven pipeline coordination

```python
@coordinate("data_collector")
def collect_customer_data():
    data = scrape_multiple_sources()
    emit("data_collection_complete", {"dataset": data})
    return data

@when("data_collection_complete")
def start_analysis(event_data):
    dataset = event_data['dataset']
    analysis_agent(dataset)  # Only starts when collection is done

@coordinate("data_analyzer")
def analysis_agent(dataset):
    return perform_analysis(dataset)
```

### Multiple agents hitting OpenAI rate limits and failing

**Problem:** Several research agents calling OpenAI API simultaneously, exceeding rate limits  
**Solution:** Use API resource lock to queue requests safely

```python
@coordinate("market_researcher", lock_name="openai_api")
def research_market_trends(industry):
    # Only one agent can call OpenAI API at a time
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Research {industry} trends"}]
    )
    return response

@coordinate("competitor_researcher", lock_name="openai_api")
def research_competitors(company):
    # Waits for market_researcher to finish before making API call
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Analyze {company} competitors"}]
    )
    return response
```

### Multiple agents updating the same customer record

**Problem:** Database corruption from concurrent updates  
**Solution:** Lock per customer during updates

```python
@coordinate("profile_updater", lock_name="customer_456")
def update_profile(customer_id, new_data):
    # Only one agent can update this customer at a time
    return db.update_customer(customer_id, new_data)

@coordinate("preference_updater", lock_name="customer_456")
def update_preferences(customer_id, preferences):
    # Waits for profile update to complete
    return db.update_preferences(customer_id, preferences)
```

## Installation & Requirements

**Python Support**: 3.9+ (tested on 3.9, 3.10, 3.11, 3.12)

```bash
pip install agentdiff-coordination
```

## Documentation

- **[Quick Start Guide](https://github.com/agentdiff/agentdiff-coordination/docs/quickstart.md)** - Get up and running in 5 minutes
- **[API Reference](https://github.com/agentdiff/agentdiff-coordination/docs/api-reference.md)** - Complete function documentation
- **[Configuration Guide](https://github.com/agentdiff/agentdiff-coordination/docs/configuration.md)** - Environment variables and settings
- **[Examples](https://github.com/agentdiff/agentdiff-coordination/examples/)** - Real-world agent coordination patterns

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Stop Debugging, Start Building

**AgentDiff helps developers who are tired of:**

- Debugging framework internals instead of building features
- Spending days on concurrency issues that should take minutes
- Complex abstractions that hide simple coordination problems
- Framework lock-in that makes migration painful

**Ready to fix your concurrency issues?**

```bash
pip install agentdiff-coordination
```

## About AgentDiff

AgentDiff builds practical tools for AI developers who are tired of framework complexity. This coordination library was built after seeing too many developers waste weeks debugging concurrency instead of building agents.

- **GitHub**: [https://github.com/agentdiff](https://github.com/agentdiff)
- **Issues**: [Report bugs and request features](https://github.com/agentdiff/agentdiff-coordination/issues)
- **Community**: Share your coordination wins and debugging horror stories

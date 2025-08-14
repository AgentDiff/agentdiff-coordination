#!/usr/bin/env python3
"""
Multi-LLM Agent Coordination Demo

Shows AgentDiff coordinating multiple AI agents using different LLM providers.
Prevents API rate limits and coordinates agent workflows.

Demonstrates real AI agent coordination scenarios:
- Research agent (OpenAI GPT-4)
- Fact-checker agent (Anthropic Claude)
- Summary agent (OpenAI GPT-3.5-turbo)
- Editor agent (coordinated workflow)

Requires API keys: OPENAI_API_KEY, ANTHROPIC_API_KEY
"""

import os
import time
from agentdiff_coordination import coordinate, when, emit
from dotenv import load_dotenv


load_dotenv()

# Check for required API keys
missing_keys = []
if not os.getenv("OPENAI_API_KEY"):
    missing_keys.append("OPENAI_API_KEY")
if not os.getenv("ANTHROPIC_API_KEY"):
    missing_keys.append("ANTHROPIC_API_KEY")

if missing_keys:
    print("Missing required API keys:")
    for key in missing_keys:
        print(f"   export {key}=your_key_here")
    print("\nThis demo shows real AI agent coordination with actual LLM calls.")
    exit(1)

# Import LLM clients after checking keys
try:
    import openai
    import anthropic

    openai_client = openai.OpenAI()
    anthropic_client = anthropic.Anthropic()

    print("LLM clients initialized")
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Install with: pip install openai anthropic")
    exit(1)

print("Multi-LLM Agent Coordination Demo")
print("Coordinating OpenAI + Anthropic agents")
print("=" * 50)

# Global state for agent workflow
workflow_state = {
    "topic": None,
    "research": None,
    "fact_check": None,
    "summary": None,
    "final_report": None,
}


@coordinate("research_agent", lock_name="openai_api")
def research_agent(topic: str):
    """Research agent using OpenAI GPT-4"""
    print(f"Research Agent: Investigating '{topic}'")

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a thorough research assistant. Provide detailed, factual research.",
                },
                {"role": "user", "content": f"Research this topic thoroughly: {topic}"},
            ],
            max_tokens=500,
            temperature=0.3,
        )

        research_result = response.choices[0].message.content
        workflow_state["research"] = research_result

        return {
            "topic": topic,
            "research": research_result,
            "model": "gpt-4",
            "tokens": response.usage.total_tokens,
        }

    except Exception as e:
        raise Exception(f"Research agent failed: {e}")


@coordinate("fact_checker_agent", lock_name="anthropic_api")
def fact_checker_agent(research_data: str):
    """Fact-checking agent using Anthropic Claude"""
    print("Fact-Checker Agent: Verifying research accuracy")

    try:
        response = anthropic_client.messages.create(
            model="claude-opus-4-1-20250805",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"Fact-check this research for accuracy and identify any potential issues:\n\n{research_data}",
                }
            ],
        )

        fact_check_result = response.content[0].text
        workflow_state["fact_check"] = fact_check_result

        return {
            "fact_check": fact_check_result,
            "model": "claude-3-sonnet",
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

    except Exception as e:
        raise Exception(f"Fact-checker agent failed: {e}")


@coordinate("summary_agent", lock_name="openai_api")
def summary_agent(research: str, fact_check: str):
    """Summary agent using OpenAI GPT-3.5-turbo"""
    print("Summary Agent: Creating final summary")

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Create clear, concise summaries combining research with fact-checking insights.",
                },
                {
                    "role": "user",
                    "content": f"Create a summary combining this research:\n{research}\n\nWith these fact-checking notes:\n{fact_check}",
                },
            ],
            max_tokens=300,
            temperature=0.5,
        )

        summary_result = response.choices[0].message.content
        workflow_state["summary"] = summary_result

        return {
            "summary": summary_result,
            "model": "gpt-3.5-turbo",
            "tokens": response.usage.total_tokens,
        }

    except Exception as e:
        raise Exception(f"Summary agent failed: {e}")


@coordinate("editor_agent")
def editor_agent(workflow_data: dict):
    """Editor agent that compiles final report"""
    print("Editor Agent: Compiling final report")

    final_report = f"""
    # Research Report: {workflow_data['topic']}

    ## Research Findings {workflow_data['research']}

    ## Fact-Check Review {workflow_data['fact_check']}

    ## Executive Summary {workflow_data['summary']}

    ---
    *Report generated by coordinated AI agents*
    *Research: GPT-4 | Fact-Check: Claude-3 | Summary: GPT-3.5-turbo*
    """

    workflow_state["final_report"] = final_report
    return {"report": final_report, "length": len(final_report)}


# Event handlers for agent coordination
@when("research_agent_complete")
def handle_research_complete(event_data):
    """Start fact-checking when research completes"""
    result = event_data["result"]
    duration = event_data["duration"]

    print(f"Research completed ({result['tokens']} tokens, {duration:.1f}s)")

    # Chain to fact-checker
    fact_checker_agent(result["research"])


@when("fact_checker_agent_complete")
def handle_fact_check_complete(event_data):
    """Start summary when fact-checking completes"""
    result = event_data["result"]
    duration = event_data["duration"]

    print(
        f"Fact-check completed ({result['input_tokens']}→{result['output_tokens']} tokens, {duration:.1f}s)"
    )

    # Chain to summary (need both research and fact-check)
    research = workflow_state["research"]
    fact_check = result["fact_check"]
    summary_agent(research, fact_check)


@when("summary_agent_complete")
def handle_summary_complete(event_data):
    """Start editor when summary completes"""
    result = event_data["result"]
    duration = event_data["duration"]

    print(f"Summary completed ({result['tokens']} tokens, {duration:.1f}s)")

    # Chain to editor with all workflow data
    editor_data = {
        "topic": workflow_state["topic"],
        "research": workflow_state["research"],
        "fact_check": workflow_state["fact_check"],
        "summary": result["summary"],
    }
    editor_agent(editor_data)


@when("editor_agent_complete")
def handle_editor_complete(event_data):
    """Handle final report completion"""
    result = event_data["result"]
    duration = event_data["duration"]

    print(f"Final report completed ({result['length']} chars, {duration:.1f}s)")
    print("\n" + "=" * 60)
    print("FINAL AGENT REPORT")
    print("=" * 60)
    print(workflow_state["final_report"])

    # Emit completion event
    emit(
        "agent_workflow_complete",
        {"topic": workflow_state["topic"], "report_length": result["length"]},
    )


@when("*_failed")
def handle_agent_failure(event_data):
    """Handle any agent failures"""
    error = event_data["error"]
    duration = event_data["duration"]

    print(f"Agent failed: {error} ({duration:.1f}s)")

    # Could implement retry logic here
    emit("agent_workflow_failed", {"error": str(error)})


@when("agent_workflow_complete")
def handle_workflow_success(event_data):
    """Handle successful workflow completion"""
    topic = event_data["topic"]
    length = event_data["report_length"]

    print(f"\nWorkflow completed successfully")
    print(f"   Topic: {topic}")
    print(f"   Report: {length} characters")
    print(f"   Agents executed: Research → Fact-Check → Summary → Editor")

    print(f"\nExecution summary:")
    print(f"   - All 4 agents completed without errors")
    print(f"   - Event-driven chain executed in sequence")
    print(f"   - Final report generated: {length} characters")


@when("agent_workflow_failed")
def handle_workflow_failure(event_data):
    """Handle workflow failures"""
    error = event_data["error"]
    print(f"\nWorkflow failed: {error}")

    print(f"\nFailure details:")
    print(f"   - Error occurred during agent execution")
    print(f"   - Remaining agents in chain were not executed")
    print(f"   - Error was captured and handled by event system")


def run_agent_workflow(topic: str):
    """Run the complete multi-agent workflow"""
    print(f"\nStarting Multi-Agent Workflow")
    print(f"Topic: {topic}")
    print(f"Planned flow: Research → Fact-Check → Summary → Editor")
    print(f"Resource locks: OpenAI API, Anthropic API")

    workflow_state["topic"] = topic

    # Start the workflow
    research_agent(topic)

    # Wait for complete workflow with proper completion detection
    print("\nWaiting for agent workflow to complete...")
    
    timeout = 120  # seconds
    start_time = time.time()
    
    while workflow_state["final_report"] is None and (time.time() - start_time) < timeout:
        time.sleep(0.5)
    
    if workflow_state["final_report"] is None:
        print(f"Workflow timeout after {timeout}s - agents may still be running")
    else:
        # Give a moment for final event handlers to complete
        time.sleep(1)


if __name__ == "__main__":
    try:
        # Example topics for testing
        test_topics = [
            "The impact of AI agents on software development",
            "Best practices for LLM API rate limiting",
            "Multi-agent coordination in production systems",
        ]

        selected_topic = test_topics[0]

        run_agent_workflow(selected_topic)

        # Success/failure messages now printed by event handlers
        # This ensures they only show when workflow actually completes

    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo failed: {e}")

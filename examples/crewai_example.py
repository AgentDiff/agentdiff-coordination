#!/usr/bin/env python3
"""
CrewAI + AgentDiff Coordination Example

Shows how to add AgentDiff coordination to existing CrewAI workflows
to prevent race conditions, manage API limits, and provide better observability.

Without AgentDiff:
- CrewAI agents might conflict on API resources
- No coordination between parallel tasks
- Limited visibility into agent execution

With AgentDiff:
- Resource locks prevent API conflicts
- Event-driven coordination between agents
- Full lifecycle monitoring and error handling
"""

import os
import time
from agentdiff_coordination import coordinate, when, emit
from dotenv import load_dotenv

load_dotenv()

# Global workflow state for coordination
workflow_state = {
    "product": None,
    "research_result": None,
    "content_result": None,
    "strategy_result": None,
    "crew_completed": False
}


@coordinate("market_researcher", lock_name="openai_api")
def coordinated_market_research(product: str, target_audience: str):
    """Market research with AgentDiff coordination"""
    print(f"Market Research Agent: Analyzing market for {product}")
    
    try:
        from crewai import Agent, Task, Crew
        
        # Create specialized market research agent
        market_researcher = Agent(
            role="Market Research Specialist",
            goal="Analyze market trends and customer preferences",
            backstory="""You are an expert at understanding market dynamics and consumer behavior.""",
            verbose=True,
        )

        research_task = Task(
            description=f"""Research the target market for our new {product}.
            Focus on {target_audience}. Analyze competitor strategies, pricing models, 
            and customer pain points. Provide specific insights and recommendations.""",
            expected_output="Comprehensive market research report with actionable insights",
            agent=market_researcher,
        )

        # Single-agent crew for this task
        research_crew = Crew(
            agents=[market_researcher],
            tasks=[research_task],
            verbose=True,
        )

        result = research_crew.kickoff()
        workflow_state["research_result"] = result
        
        return {
            "research_findings": str(result),
            "agent": "market_researcher",
            "product": product,
            "target_audience": target_audience
        }

    except ImportError:
        raise Exception("CrewAI not installed. Install with: pip install crewai")
    except Exception as e:
        raise Exception(f"Market research failed: {e}")


@coordinate("content_creator", lock_name="openai_api")
def coordinated_content_creation(research_data: dict):
    """Content creation with AgentDiff coordination"""
    print("Content Creator Agent: Developing marketing content")
    
    try:
        from crewai import Agent, Task, Crew
        
        content_creator = Agent(
            role="Creative Content Designer", 
            goal="Create engaging marketing content",
            backstory="""You specialize in creating content that resonates with target audiences.""",
            verbose=True,
        )

        content_task = Task(
            description=f"""Based on these research findings:
            
            {research_data['research_findings']}
            
            Create compelling marketing content for {research_data['product']} 
            targeting {research_data['target_audience']}. Include:
            - Catchy headlines
            - Key value propositions  
            - Campaign concepts
            - Call-to-action phrases""",
            expected_output="Marketing content package with headlines, messages, and campaign concepts",
            agent=content_creator,
        )

        content_crew = Crew(
            agents=[content_creator],
            tasks=[content_task],
            verbose=True,
        )

        result = content_crew.kickoff()
        workflow_state["content_result"] = result
        
        return {
            "content_package": str(result),
            "agent": "content_creator",
            "based_on_research": True
        }

    except Exception as e:
        raise Exception(f"Content creation failed: {e}")


@coordinate("campaign_manager", lock_name="openai_api")
def coordinated_campaign_strategy(research_data: dict, content_data: dict):
    """Campaign strategy with AgentDiff coordination"""
    print("Campaign Manager Agent: Developing strategy")
    
    try:
        from crewai import Agent, Task, Crew
        
        campaign_manager = Agent(
            role="Marketing Campaign Manager",
            goal="Orchestrate and optimize marketing campaigns", 
            backstory="""You have extensive experience in managing successful marketing campaigns.""",
            verbose=True,
        )

        strategy_task = Task(
            description=f"""Develop a comprehensive campaign strategy using:
            
            RESEARCH INSIGHTS:
            {research_data['research_findings']}
            
            CONTENT ASSETS:
            {content_data['content_package']}
            
            Create an actionable campaign plan with:
            - Campaign timeline and phases
            - Budget allocation recommendations
            - Channel strategy (digital, social, etc.)
            - Success metrics and KPIs
            - Risk mitigation strategies""",
            expected_output="Detailed campaign strategy document with timeline, budget, and implementation plan",
            agent=campaign_manager,
        )

        strategy_crew = Crew(
            agents=[campaign_manager],
            tasks=[strategy_task], 
            verbose=True,
        )

        result = strategy_crew.kickoff()
        workflow_state["strategy_result"] = result
        
        return {
            "campaign_strategy": str(result),
            "agent": "campaign_manager",
            "integrates_research_and_content": True
        }

    except Exception as e:
        raise Exception(f"Campaign strategy failed: {e}")


# Event handlers for coordinated workflow
@when("market_researcher_complete")
def handle_research_complete(event_data):
    """Start content creation when research completes"""
    result = event_data["result"]
    duration = event_data["duration"]
    
    print(f"Market research completed ({duration:.1f}s)")
    print("Triggering content creation...")
    
    # Chain to content creator
    coordinated_content_creation(result)


@when("content_creator_complete") 
def handle_content_complete(event_data):
    """Start campaign strategy when content completes"""
    result = event_data["result"]
    duration = event_data["duration"]
    
    print(f"Content creation completed ({duration:.1f}s)")
    print("Triggering campaign strategy...")
    
    # Chain to campaign strategy (needs both research and content)
    research_data = {
        "research_findings": workflow_state["research_result"],
        "product": workflow_state["product"],
        "target_audience": "Business professionals"
    }
    coordinated_campaign_strategy(research_data, result)


@when("campaign_manager_complete")
def handle_strategy_complete(event_data):
    """Handle final campaign strategy completion"""
    result = event_data["result"]
    duration = event_data["duration"]
    
    print(f"Campaign strategy completed ({duration:.1f}s)")
    workflow_state["crew_completed"] = True
    
    # Emit workflow completion
    emit("crewai_workflow_complete", {
        "research": workflow_state["research_result"],
        "content": workflow_state["content_result"], 
        "strategy": result["campaign_strategy"],
        "product": workflow_state["product"]
    })


@when("*_failed")
def handle_agent_failure(event_data):
    """Handle any agent failures in the CrewAI workflow"""
    error = event_data["error"]
    duration = event_data["duration"]
    
    print(f"CrewAI Agent failed: {error} ({duration:.1f}s)")
    emit("crewai_workflow_failed", {"error": str(error)})


@when("crewai_workflow_complete")
def handle_workflow_success(event_data):
    """Handle successful CrewAI workflow completion"""
    print(f"\nCrewAI workflow completed successfully")
    print("=" * 60)
    print("MARKETING CAMPAIGN RESULTS")
    print("=" * 60)
    
    print(f"\nMARKET RESEARCH:")
    print(f"{event_data['research']}")
    
    print(f"\nCONTENT PACKAGE:")
    print(f"{event_data['content']}")
    
    print(f"\nCAMPAIGN STRATEGY:")
    print(f"{event_data['strategy']}")
    
    print(f"\nWorkflow execution summary:")
    print(f"   - 3 CrewAI agents completed sequentially")
    print(f"   - Event-driven coordination between agents")
    print(f"   - Resource locks applied to OpenAI API calls")
    print(f"   - Full lifecycle logging and monitoring active")


@when("crewai_workflow_failed")
def handle_workflow_failure(event_data):
    """Handle CrewAI workflow failures"""
    error = event_data["error"]
    print(f"\nCrewAI workflow failed: {error}")
    print(f"   - Error captured by event system")
    print(f"   - Workflow execution halted")


def advanced_crewai_with_agentdiff():
    """CrewAI workflow enhanced with AgentDiff coordination"""
    
    try:
        import crewai
        print("CrewAI available")
    except ImportError:
        print("CrewAI not installed. Install with: pip install crewai")
        return None
    
    print("CrewAI + AgentDiff Coordination Demo")
    print("Preventing agent conflicts and adding observability")
    print("=" * 50)
    
    # Set workflow parameters
    product = "AI-Powered Productivity Tool"
    target_audience = "Business professionals"
    
    workflow_state["product"] = product
    
    print(f"\nStarting Coordinated CrewAI Workflow")
    print(f"Product: {product}")
    print(f"Target: {target_audience}")
    print("Flow: Research → Content → Strategy")
    print("API Protection: OpenAI rate limits managed")
    
    # Start the coordinated workflow
    coordinated_market_research(product, target_audience)
    
    # Wait for complete workflow
    print("\nWaiting for coordinated agent workflow...")
    
    # Wait for completion with timeout
    timeout = 60  # seconds
    start_time = time.time()
    
    while not workflow_state["crew_completed"] and (time.time() - start_time) < timeout:
        time.sleep(1)
    
    if not workflow_state["crew_completed"]:
        print(" Workflow timeout - agents may still be running")
    
    return workflow_state


if __name__ == "__main__":
    try:
        advanced_crewai_with_agentdiff()
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo failed: {e}")

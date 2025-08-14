"""
Integration tests for AgentDiff Coordination.

Tests the full coordination flow with real scenarios.
"""

import pytest
import time
import threading
from agentdiff_coordination import coordinate, when, emit


class TestAgentCoordinationFlow:
    """Test full agent coordination workflows"""
    
    def test_simple_agent_workflow(self):
        """Test a simple agent workflow with coordination"""
        workflow_events = []
        
        @when("processor_started")
        def track_start(event_data):
            workflow_events.append("started")
        
        @when("processor_complete") 
        def track_completion(event_data):
            workflow_events.append("complete")
            workflow_events.append(f"result:{event_data['result']}")
        
        # Give time for event subscriptions
        time.sleep(0.1)
        
        @coordinate("processor")
        def process_data(data):
            # Simulate some processing
            time.sleep(0.05)
            return f"processed_{data}"
        
        # Execute the agent
        result = process_data("test_input")
        
        # Give time for event processing
        time.sleep(0.2)
        
        # Verify the workflow
        assert result == "processed_test_input"
        assert "started" in workflow_events
        assert "complete" in workflow_events
        assert "result:processed_test_input" in workflow_events
    
    def test_multi_agent_coordination(self):
        """Test coordination between multiple agents"""
        execution_log = []
        
        @coordinate("agent_a", lock_name="shared_resource")
        def agent_a(task_id):
            execution_log.append(f"a_start_{task_id}")
            time.sleep(0.1)
            execution_log.append(f"a_end_{task_id}")
            return f"a_result_{task_id}"
        
        @coordinate("agent_b", lock_name="shared_resource")
        def agent_b(task_id):
            execution_log.append(f"b_start_{task_id}")
            time.sleep(0.1)
            execution_log.append(f"b_end_{task_id}")
            return f"b_result_{task_id}"
        
        # Run agents concurrently
        results = []
        
        def run_agent(agent_func, task_id):
            result = agent_func(task_id)
            results.append(result)
        
        threads = [
            threading.Thread(target=run_agent, args=(agent_a, 1)),
            threading.Thread(target=run_agent, args=(agent_b, 2)),
            threading.Thread(target=run_agent, args=(agent_a, 3)),
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify results
        assert len(results) == 3
        assert "a_result_1" in results
        assert "b_result_2" in results
        assert "a_result_3" in results
        
        # Verify no interleaving (resource protection worked)
        assert len(execution_log) == 6
        
        # Each agent should complete fully before another starts
        for i in range(0, len(execution_log), 2):
            start_event = execution_log[i]
            end_event = execution_log[i + 1]
            
            # Extract agent and task from start event
            agent = start_event.split('_')[0]
            task = start_event.split('_')[-1]
            
            # End event should match
            expected_end = f"{agent}_end_{task}"
            assert end_event == expected_end
    
    def test_event_driven_agent_chain(self):
        """Test agents chaining via events"""
        chain_log = []
        
        @coordinate("collector")
        def data_collector():
            chain_log.append("collector_executed")
            return ["data1", "data2", "data3"]
        
        @coordinate("processor")
        def data_processor(raw_data):
            chain_log.append("processor_executed")
            return [item.upper() for item in raw_data]
        
        @coordinate("saver")
        def data_saver(processed_data):
            chain_log.append("saver_executed")
            return f"saved_{len(processed_data)}_items"
        
        # Set up event chain
        @when("collector_complete")
        def handle_collection_complete(event_data):
            raw_data = event_data['result']
            data_processor(raw_data)
        
        @when("processor_complete")
        def handle_processing_complete(event_data):
            processed_data = event_data['result']
            data_saver(processed_data)
        
        final_results = []
        
        @when("saver_complete")
        def handle_save_complete(event_data):
            final_results.append(event_data['result'])
        
        # Give time for event subscriptions
        time.sleep(0.1)
        
        # Start the chain
        collector_result = data_collector()
        
        # Wait for chain to complete
        time.sleep(0.5)
        
        # Verify the chain executed
        assert collector_result == ["data1", "data2", "data3"]
        assert "collector_executed" in chain_log
        assert "processor_executed" in chain_log
        assert "saver_executed" in chain_log
        assert len(final_results) == 1
        assert final_results[0] == "saved_3_items"
    
    def test_error_isolation(self):
        """Test that agent errors are properly isolated"""
        execution_log = []
        error_events = []
        
        @coordinate("failing_agent")
        def failing_agent():
            execution_log.append("failing_agent_executed")
            raise ValueError("Intentional test failure")
        
        @coordinate("working_agent")
        def working_agent():
            execution_log.append("working_agent_executed")
            return "success"
        
        @when("failing_agent_failed")
        def handle_failure(event_data):
            error_events.append(event_data)
        
        # Give time for event subscriptions
        time.sleep(0.1)
        
        # Test failing agent
        with pytest.raises(ValueError, match="Intentional test failure"):
            failing_agent()
        
        # Test that working agent still works
        result = working_agent()
        
        # Give time for event processing
        time.sleep(0.1)
        
        assert result == "success"
        assert "failing_agent_executed" in execution_log
        assert "working_agent_executed" in execution_log
        assert len(error_events) == 1
        assert "error" in error_events[0]
        assert "Intentional test failure" in error_events[0]["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
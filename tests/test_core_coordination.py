"""
Core coordination tests for AgentDiff Coordination.

Tests the essential @coordinate decorator and basic coordination functionality.
"""

import pytest
import time
import threading
from unittest.mock import patch, MagicMock

from agentdiff_coordination import coordinate, when, emit
from agentdiff_coordination.coordination import AgentLock
from agentdiff_coordination.exceptions import CoordinationTimeoutError


class TestCoordinateDecorator:
    """Test the @coordinate decorator core functionality"""
    
    def test_coordinate_basic_execution(self):
        """Test basic @coordinate decorator execution"""
        executed = []
        
        @coordinate("test_agent")
        def test_function(value):
            executed.append(value)
            return f"result_{value}"
        
        result = test_function("hello")
        
        assert result == "result_hello"
        assert executed == ["hello"]
    
    def test_coordinate_with_lock(self):
        """Test @coordinate with resource locking"""
        execution_order = []
        
        @coordinate("test_agent", lock_name="shared_resource")
        def test_function(worker_id):
            execution_order.append(f"start_{worker_id}")
            time.sleep(0.1)  # Simulate work
            execution_order.append(f"end_{worker_id}")
            return worker_id
        
        # Run multiple workers in parallel
        threads = []
        results = []
        
        def worker(worker_id):
            result = test_function(worker_id)
            results.append(result)
        
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify sequential execution (no interleaving)
        assert len(execution_order) == 6
        
        # Check that each worker completes fully before the next starts
        # There should be no interleaving of start/end pairs
        def check_no_interleaving(order):
            """Check that start_X is immediately followed by end_X for each worker"""
            for i in range(0, len(order), 2):
                start_event = order[i]
                end_event = order[i + 1]
                # Extract worker ID from start_X and end_X
                start_id = start_event.split('_')[1]
                end_id = end_event.split('_')[1]
                if start_id != end_id:
                    return False
            return True
        
        # The test should pass regardless of thread execution order,
        # as long as there's no interleaving within each worker
        assert check_no_interleaving(execution_order), f"Interleaving detected in execution order: {execution_order}"
        
        assert len(results) == 3
        assert set(results) == {0, 1, 2}

    def test_coordinate_exception_handling(self):
        """Test @coordinate decorator exception handling"""
        
        @coordinate("failing_agent")
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            failing_function()


class TestEventSystem:
    """Test the event system (@when, emit)"""
    
    def test_basic_event_emission_and_handling(self):
        """Test basic event emission and handling"""
        received_events = []
        
        @when("test_event")
        def handle_event(event_data):
            received_events.append(event_data)
        
        # Give time for subscription to register
        time.sleep(0.1)
        
        emit("test_event", {"message": "hello"})
        
        # Give time for event processing
        time.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0]["message"] == "hello"
    
    def test_coordinate_lifecycle_events(self):
        """Test that @coordinate emits lifecycle events"""
        start_events = []
        complete_events = []
        
        @when("test_agent_started")
        def handle_start(event_data):
            start_events.append(event_data)
        
        @when("test_agent_complete")
        def handle_complete(event_data):
            complete_events.append(event_data)
        
        # Give time for subscriptions
        time.sleep(0.1)
        
        @coordinate("test_agent")
        def test_function(value):
            return f"processed_{value}"
        
        result = test_function("test")
        
        # Give time for event processing
        time.sleep(0.2)
        
        assert result == "processed_test"
        assert len(start_events) == 1
        assert len(complete_events) == 1
        
        # Check event data structure
        assert "args" in start_events[0]
        assert "timestamp" in start_events[0]
        assert "result" in complete_events[0]
        assert "duration" in complete_events[0]
        assert complete_events[0]["result"] == "processed_test"


class TestAgentLock:
    """Test the AgentLock coordination primitive"""
    
    def test_agent_lock_basic_usage(self):
        """Test basic AgentLock usage"""
        execution_order = []
        
        def worker(worker_id):
            with AgentLock("test_resource"):
                execution_order.append(f"start_{worker_id}")
                time.sleep(0.05)
                execution_order.append(f"end_{worker_id}")
        
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify no interleaving occurred
        assert len(execution_order) == 6
        for i in range(0, 6, 2):
            worker_id = execution_order[i].split("_")[1]
            assert execution_order[i+1] == f"end_{worker_id}"
    
    def test_agent_lock_timeout(self):
        """Test AgentLock timeout functionality"""
        
        def long_running_task():
            with AgentLock("test_resource"):
                time.sleep(0.5)
        
        def quick_task():
            with AgentLock("test_resource", timeout=0.1):
                pass
        
        # Start long running task
        thread1 = threading.Thread(target=long_running_task)
        thread1.start()
        
        time.sleep(0.1)  # Ensure first lock is acquired
        
        # Try to acquire lock with short timeout
        with pytest.raises(CoordinationTimeoutError):
            quick_task()
        
        thread1.join()
    
    def test_agent_lock_different_resources(self):
        """Test that different resource locks don't interfere"""
        execution_order = []
        
        def worker_a():
            with AgentLock("resource_a"):
                execution_order.append("a_start")
                time.sleep(0.1)
                execution_order.append("a_end")
        
        def worker_b():
            with AgentLock("resource_b"):
                execution_order.append("b_start")
                time.sleep(0.1)
                execution_order.append("b_end")
        
        thread_a = threading.Thread(target=worker_a)
        thread_b = threading.Thread(target=worker_b)
        
        thread_a.start()
        thread_b.start()
        
        thread_a.join()
        thread_b.join()
        
        # Both should run concurrently
        assert len(execution_order) == 4
        assert "a_start" in execution_order
        assert "a_end" in execution_order
        assert "b_start" in execution_order
        assert "b_end" in execution_order


class TestConfiguration:
    """Test configuration system"""
    
    def test_config_import(self):
        """Test that config can be imported and accessed"""
        from agentdiff_coordination.config import config
        
        # Basic config properties should exist
        assert hasattr(config, 'persistence_backend')
        assert hasattr(config, 'data_dir')
        assert hasattr(config, 'log_level')
    
    @patch.dict('os.environ', {
        'AGENTDIFF_COORDINATION_PERSISTENCE_BACKEND': 'redis',
        'AGENTDIFF_COORDINATION_LOG_LEVEL': 'DEBUG'
    })
    def test_config_environment_variables(self):
        """Test that config reads environment variables"""
        # Need to reload config to pick up env changes
        import importlib
        from agentdiff_coordination import config as config_module
        importlib.reload(config_module)
        
        from agentdiff_coordination.config import config
        
        assert config.persistence_backend == 'redis'
        assert config.log_level == 'DEBUG'


class TestPersistenceIntegration:
    """Test basic persistence integration"""
    
    def test_file_persistence_initialization(self):
        """Test that file persistence can be initialized"""
        from agentdiff_coordination.persistence.file_persistence import FilePersistence
        
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence = FilePersistence(temp_dir)
            
            # Should create necessary directories
            assert persistence.coordination_dir.exists()
            assert persistence.session_file.name.startswith("session_")
    
    def test_message_storage(self):
        """Test basic message storage functionality"""
        from agentdiff_coordination.persistence.file_persistence import FilePersistence
        from agentdiff_coordination.persistence.persistence_interface import Message
        
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence = FilePersistence(temp_dir)
            
            message = Message(
                topic="test_topic",
                payload={"test": "data"},
                timestamp=time.time(),
                message_id="test_id"
            )
            
            success = persistence.store_message(message)
            assert success
            
            # Should be able to read back
            assert persistence.session_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
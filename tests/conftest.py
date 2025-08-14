"""
Pytest configuration for AgentDiff Coordination tests.
"""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment with clean configuration"""
    # Use in-memory backend for tests to avoid file system side effects
    os.environ["AGENTDIFF_COORDINATION_PERSISTENCE_BACKEND"] = "inmemory"
    os.environ["AGENTDIFF_COORDINATION_LOG_LEVEL"] = "WARNING"  # Reduce test noise
    
    yield
    
    # Cleanup
    for key in list(os.environ.keys()):
        if key.startswith("AGENTDIFF_COORDINATION_"):
            del os.environ[key]


@pytest.fixture
def temp_data_dir():
    """Provide a temporary directory for tests that need file system access"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def clean_coordination_state():
    """Reset coordination state between tests"""
    # Cleanup any global state that might interfere with tests
    from agentdiff_coordination.decorators import cleanup_all_subscriptions
    
    yield
    
    # Cleanup after test
    try:
        cleanup_all_subscriptions()
    except:
        pass  # Don't fail tests if cleanup fails


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset any global state before each test"""
    # Reset broker state if needed
    try:
        from agentdiff_coordination.pubsub import pubsub_broker
        if hasattr(pubsub_broker, '_default_broker') and pubsub_broker._default_broker:
            pubsub_broker._default_broker = None
    except:
        pass
    
    yield
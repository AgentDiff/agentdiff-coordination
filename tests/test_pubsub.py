"""
Tests for the pub/sub system.
"""

import pytest
import time
import threading
from unittest.mock import Mock

from agentdiff_coordination.pubsub.pubsub_broker import EmbeddedBroker, Message


class TestEmbeddedBroker:
    """Test the embedded broker functionality"""
    
    def test_basic_publish_subscribe(self):
        """Test basic publish/subscribe functionality"""
        broker = EmbeddedBroker(persistence_backend="inmemory")
        received_messages = []
        
        def message_handler(message):
            received_messages.append(message)
        
        # Subscribe
        subscriber_id = broker.subscribe("test_topic", message_handler)
        
        # Publish
        message_id = broker.publish("test_topic", {"data": "test"})
        
        # Give time for message processing
        time.sleep(0.1)
        
        assert len(received_messages) == 1
        assert received_messages[0].topic == "test_topic"
        assert received_messages[0].payload == {"data": "test"}
        
        # Cleanup
        broker.unsubscribe("test_topic", subscriber_id)
        broker.shutdown()
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers to same topic"""
        broker = EmbeddedBroker(persistence_backend="inmemory")
        received_messages_1 = []
        received_messages_2 = []
        
        def handler_1(message):
            received_messages_1.append(message)
        
        def handler_2(message):
            received_messages_2.append(message)
        
        # Subscribe multiple handlers
        sub_id_1 = broker.subscribe("test_topic", handler_1)
        sub_id_2 = broker.subscribe("test_topic", handler_2)
        
        # Publish one message
        broker.publish("test_topic", {"data": "broadcast"})
        
        time.sleep(0.1)
        
        # Both handlers should receive the message
        assert len(received_messages_1) == 1
        assert len(received_messages_2) == 1
        assert received_messages_1[0].payload == {"data": "broadcast"}
        assert received_messages_2[0].payload == {"data": "broadcast"}
        
        # Cleanup
        broker.unsubscribe("test_topic", sub_id_1)
        broker.unsubscribe("test_topic", sub_id_2)
        broker.shutdown()
    
    def test_pattern_matching(self):
        """Test wildcard pattern matching"""
        broker = EmbeddedBroker(persistence_backend="inmemory")
        received_messages = []
        
        def pattern_handler(message):
            received_messages.append(message)
        
        # Subscribe to pattern
        subscriber_id = broker.subscribe("agent.*", pattern_handler)
        
        # Publish to matching topics
        broker.publish("agent.started", {"event": "start"})
        broker.publish("agent.completed", {"event": "complete"})
        broker.publish("system.status", {"event": "status"})  # Shouldn't match
        
        time.sleep(0.1)
        
        # Should receive 2 messages (the ones matching pattern)
        assert len(received_messages) == 2
        topics = [msg.topic for msg in received_messages]
        assert "agent.started" in topics
        assert "agent.completed" in topics
        assert "system.status" not in topics
        
        # Cleanup
        broker.unsubscribe("agent.*", subscriber_id)
        broker.shutdown()
    
    def test_unsubscribe(self):
        """Test unsubscribing from topics"""
        broker = EmbeddedBroker(persistence_backend="inmemory")
        received_messages = []
        
        def message_handler(message):
            received_messages.append(message)
        
        # Subscribe
        subscriber_id = broker.subscribe("test_topic", message_handler)
        
        # Publish first message
        broker.publish("test_topic", {"data": "message1"})
        time.sleep(0.1)
        
        # Unsubscribe
        success = broker.unsubscribe("test_topic", subscriber_id)
        assert success
        
        # Publish second message - shouldn't be received
        broker.publish("test_topic", {"data": "message2"})
        time.sleep(0.1)
        
        # Should only have received first message
        assert len(received_messages) == 1
        assert received_messages[0].payload == {"data": "message1"}
        
        broker.shutdown()
    
    def test_subscriber_failure_handling(self):
        """Test handling of subscriber failures"""
        broker = EmbeddedBroker(persistence_backend="inmemory")
        
        def failing_handler(message):
            raise Exception("Handler failure")
        
        def working_handler(message):
            self.received_message = message
        
        self.received_message = None
        
        # Subscribe both handlers
        failing_sub = broker.subscribe("test_topic", failing_handler)
        working_sub = broker.subscribe("test_topic", working_handler)
        
        # Publish message
        broker.publish("test_topic", {"data": "test"})
        time.sleep(0.2)  # Give time for processing and retries
        
        # Working handler should still receive message despite failing handler
        assert self.received_message is not None
        assert self.received_message.payload == {"data": "test"}
        
        # Cleanup
        broker.unsubscribe("test_topic", failing_sub)
        broker.unsubscribe("test_topic", working_sub)
        broker.shutdown()
    
    def test_broker_stats(self):
        """Test broker statistics"""
        broker = EmbeddedBroker(persistence_backend="inmemory")
        
        def dummy_handler(message):
            pass
        
        # Subscribe to some topics
        sub1 = broker.subscribe("topic1", dummy_handler)
        sub2 = broker.subscribe("topic2", dummy_handler)
        sub3 = broker.subscribe("topic.*", dummy_handler)  # Pattern
        
        # Publish some messages
        broker.publish("topic1", {"data": "1"})
        broker.publish("topic2", {"data": "2"})
        
        stats = broker.get_stats()
        
        assert "subscribers" in stats
        assert "pattern_subscribers" in stats
        assert "total_messages" in stats
        assert "uptime_seconds" in stats
        
        assert stats["subscribers"] == 2  # topic1, topic2
        assert stats["pattern_subscribers"] == 1  # topic.*
        assert stats["total_messages"] == 2
        
        # Cleanup
        broker.unsubscribe("topic1", sub1)
        broker.unsubscribe("topic2", sub2)
        broker.unsubscribe("topic.*", sub3)
        broker.shutdown()


class TestMessage:
    """Test the Message data structure"""
    
    def test_message_creation(self):
        """Test creating a Message object"""
        timestamp = time.time()
        message = Message(
            topic="test.topic",
            payload={"key": "value"},
            timestamp=timestamp,
            message_id="test_id_123",
            sender="test_sender",
            correlation_id="corr_123"
        )
        
        assert message.topic == "test.topic"
        assert message.payload == {"key": "value"}
        assert message.timestamp == timestamp
        assert message.message_id == "test_id_123"
        assert message.sender == "test_sender"
        assert message.correlation_id == "corr_123"
        assert message.retry_count == 0  # Default value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
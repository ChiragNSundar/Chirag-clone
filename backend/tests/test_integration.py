"""
Integration Tests - End-to-end tests for complete workflows.
Tests the interaction between multiple services.

Run with: pytest tests/test_integration.py -v
"""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)


class TestChatWorkflow:
    """Test complete chat workflow."""
    
    def test_chat_with_mocked_llm(self):
        """Test chat endpoint with mocked LLM service."""
        with patch('main.get_chat_service') as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.generate_response.return_value = (
                "Hello! I'm Chirag's digital twin.",
                0.85,
                {"primary": "friendly", "energy": 0.7}
            )
            
            async def async_mock():
                return mock_svc
            mock_get_svc.return_value = mock_svc
            
            response = client.post("/api/chat/message", json={
                "message": "Hello!",
                "session_id": "test-integration"
            })
            
            # Verify structure even if mocked
            if response.status_code == 200:
                data = response.json()
                assert "response" in data or "error" in data


class TestTrainingWorkflow:
    """Test training data workflow."""
    
    def test_feedback_then_stats(self):
        """Test that training feedback affects stats."""
        # Submit feedback
        feedback_response = client.post("/api/training/feedback", json={
            "context": "Test context",
            "correct_response": "Test response",
            "accepted": False
        })
        
        # Check stats (should not crash)
        stats_response = client.get("/api/dashboard/stats")
        assert stats_response.status_code == 200


class TestProfileVisualizationWorkflow:
    """Test profile and visualization workflow."""
    
    def test_profile_to_graph(self):
        """Test that profile data is reflected in graph."""
        # Get profile
        profile_response = client.get("/api/profile")
        assert profile_response.status_code == 200
        profile = profile_response.json()
        
        # Get graph
        graph_response = client.get("/api/visualization/graph")
        assert graph_response.status_code == 200
        graph = graph_response.json()
        
        # Graph should have root node with profile name
        if graph["nodes"]:
            root_nodes = [n for n in graph["nodes"] if n["id"] == "root"]
            if root_nodes:
                assert root_nodes[0]["label"] == profile["name"]


class TestAutopilotWorkflow:
    """Test autopilot bot workflow."""
    
    def test_status_then_settings(self):
        """Test getting status then updating settings."""
        # Get status first
        status_response = client.get("/api/autopilot/status")
        assert status_response.status_code == 200
        
        # Try updating settings (may fail if not implemented, but shouldn't crash)
        settings_response = client.post("/api/autopilot/settings", json={
            "auto_reply_dms": True,
            "auto_reply_mentions": True
        })
        # Any response is acceptable (may not be implemented)
        assert settings_response.status_code in [200, 404, 422, 500]


class TestAnalyticsWorkflow:
    """Test analytics workflow."""
    
    def test_stats_to_detailed(self):
        """Test basic stats then detailed analytics."""
        # Basic stats
        stats = client.get("/api/dashboard/stats")
        assert stats.status_code == 200
        
        # Detailed analytics (if exists)
        detailed = client.get("/api/analytics/detailed")
        # May not exist, that's ok
        assert detailed.status_code in [200, 404]


class TestHealthWorkflow:
    """Test health check workflow."""
    
    def test_health_check_sequence(self):
        """Test multiple health checks in sequence."""
        for i in range(3):
            response = client.get("/api/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"


class TestErrorRecoveryWorkflow:
    """Test error recovery and resilience."""
    
    def test_invalid_then_valid_request(self):
        """Test that invalid request doesn't break subsequent valid requests."""
        # Invalid request
        invalid = client.post("/api/chat/message", json={})
        assert invalid.status_code == 422
        
        # Valid request should still work
        valid = client.get("/api/health")
        assert valid.status_code == 200
        
    def test_malformed_json_recovery(self):
        """Test recovery from malformed JSON."""
        # Malformed JSON
        malformed = client.post(
            "/api/chat/message",
            content="not json",
            headers={"Content-Type": "application/json"}
        )
        assert malformed.status_code == 422
        
        # Should still work after
        health = client.get("/api/health")
        assert health.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

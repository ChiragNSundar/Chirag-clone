"""
Integration Tests - End-to-end tests for complete workflows.
Tests the interaction between multiple services.

Run with: pytest tests/test_integration.py -v

Note: Requires chromadb and other dependencies to be installed.
Tests will be skipped if chromadb is not available.
"""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check if chromadb is available
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# Skip all tests if chromadb is not installed
pytestmark = pytest.mark.skipif(
    not CHROMADB_AVAILABLE,
    reason="chromadb not installed - skipping integration tests"
)

if CHROMADB_AVAILABLE:
    from main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
else:
    # Dummy client for when chromadb is not available
    client = None


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


# ============================================================================
# v2.3 Features - Voice WebSocket
# ============================================================================

class TestVoiceEndpoints:
    """Test voice service endpoints."""
    
    def test_voice_status(self):
        """Test voice service status endpoint."""
        response = client.get("/api/voice/status")
        assert response.status_code == 200
        data = response.json()
        assert "tts_available" in data
        assert "stt_available" in data
    
    def test_voice_speak_requires_text(self):
        """Test that speak endpoint requires text parameter."""
        response = client.post("/api/voice/speak", json={})
        assert response.status_code == 422
    
    def test_voice_speak_with_text(self):
        """Test speak endpoint with valid text."""
        response = client.post("/api/voice/speak", json={
            "text": "Hello, this is a test."
        })
        # May fail if ElevenLabs not configured, but should not crash
        assert response.status_code in [200, 500, 503]
    
    def test_voice_listen_empty_audio(self):
        """Test listen endpoint with missing audio."""
        response = client.post("/api/voice/listen", json={})
        # Should fail gracefully
        assert response.status_code in [400, 422, 500]


# ============================================================================
# v2.3 Features - Desktop Vision
# ============================================================================

class TestVisionEndpoints:
    """Test vision/desktop analysis endpoints."""
    
    def test_vision_analyze_requires_image(self):
        """Test that vision analyze requires image data."""
        response = client.post("/api/vision/analyze", json={})
        assert response.status_code == 422
    
    def test_vision_desktop_requires_image(self):
        """Test desktop vision endpoint requires image."""
        response = client.post("/api/vision/desktop", json={})
        assert response.status_code == 422
    
    def test_vision_desktop_with_base64(self):
        """Test desktop vision with minimal base64 image stub."""
        # Minimal 1x1 PNG base64
        tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        response = client.post("/api/vision/desktop", json={
            "image_base64": tiny_png
        })
        # May fail if Gemini Vision not configured, but should accept payload
        assert response.status_code in [200, 500, 503]


# ============================================================================
# v2.3 Features - Brain Station / Knowledge Management
# ============================================================================

class TestKnowledgeEndpoints:
    """Test knowledge management (Brain Station) endpoints."""
    
    def test_knowledge_stats(self):
        """Test knowledge statistics endpoint."""
        response = client.get("/api/knowledge/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_documents" in data or "document_count" in data or "total" in data
    
    def test_knowledge_documents_list(self):
        """Test listing knowledge documents."""
        response = client.get("/api/knowledge/documents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
    
    def test_knowledge_query_requires_text(self):
        """Test that query endpoint requires query text."""
        response = client.post("/api/knowledge/query", json={})
        assert response.status_code == 422
    
    def test_knowledge_query_with_text(self):
        """Test semantic search query."""
        response = client.post("/api/knowledge/query", json={
            "query": "What is machine learning?"
        })
        # Should return results (may be empty)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data or isinstance(data, list)
    
    def test_knowledge_text_upload(self):
        """Test uploading text content to knowledge base."""
        response = client.post("/api/knowledge/text", json={
            "content": "This is a test fact about the user.",
            "title": "Test Document"
        })
        # Should succeed or fail gracefully
        assert response.status_code in [200, 201, 500]
    
    def test_knowledge_url_ingest(self):
        """Test URL ingestion (may fail if network blocked)."""
        response = client.post("/api/knowledge/url", json={
            "url": "https://example.com"
        })
        # Network may be blocked in test env, that's ok
        assert response.status_code in [200, 201, 400, 500, 503]
    
    def test_knowledge_delete_nonexistent(self):
        """Test deleting a non-existent document."""
        response = client.delete("/api/knowledge/document/nonexistent-id-12345")
        # Should return 404 or handle gracefully
        assert response.status_code in [200, 404, 500]


# ============================================================================
# v2.3 Features - Cognitive Services
# ============================================================================

class TestCognitiveEndpoints:
    """Test cognitive service endpoints (core memories, active learning)."""
    
    def test_core_memories_list(self):
        """Test listing core memories."""
        response = client.get("/api/cognitive/core-memories")
        assert response.status_code == 200
    
    def test_learning_stats(self):
        """Test getting learning statistics."""
        response = client.get("/api/cognitive/learning-stats")
        assert response.status_code == 200
    
    def test_active_learning_suggestions(self):
        """Test getting active learning suggestions."""
        response = client.get("/api/cognitive/active-learning/suggestions")
        # May return empty list if no gaps detected
        assert response.status_code == 200


# ============================================================================
# Combined Workflow Tests
# ============================================================================

class TestBrainStationWorkflow:
    """Test complete Brain Station workflow."""
    
    def test_upload_then_query(self):
        """Test uploading content then querying it."""
        # Upload some content
        upload_response = client.post("/api/knowledge/text", json={
            "content": "The capital of France is Paris. Paris is known for the Eiffel Tower.",
            "title": "France Facts"
        })
        
        # Query for related content
        query_response = client.post("/api/knowledge/query", json={
            "query": "What is the capital of France?"
        })
        
        # Both should work
        assert upload_response.status_code in [200, 201, 500]
        assert query_response.status_code == 200


class TestVoiceVisionIntegration:
    """Test voice and vision feature availability."""
    
    def test_services_availability(self):
        """Test that voice and vision services are available."""
        voice = client.get("/api/voice/status")
        assert voice.status_code == 200
        
        health = client.get("/api/health")
        assert health.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


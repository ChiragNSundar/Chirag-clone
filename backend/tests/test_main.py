
from fastapi.testclient import TestClient
from main import app
import pytest

client = TestClient(app)

def test_health_check():
    """Verify API health endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["framework"] == "FastAPI"

def test_chat_endpoint_structure():
    """Verify chat endpoint accepts valid payload structure."""
    # Note: We won't test actual LLM generation here to avoid API costs/latency during CI
    # but we can check if it validates input correctly.
    
    # Missing 'message' field should fail
    response = client.post("/api/chat/message", json={"session_id": "test"})
    assert response.status_code == 422
    
def test_dashboard_stats():
    """Verify dashboard stats endpoint returns correct schema."""
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert "personality_completion" in data
    assert "facts_count" in data

def test_profile_endpoint():
    """Verify profile endpoint returns personality data."""
    response = client.get("/api/profile")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "summary" in data

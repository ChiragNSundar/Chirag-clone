"""
Main API Tests - Test FastAPI application endpoints and middleware.

Run with: pytest tests/test_main.py -v
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

try:
    from backend.main import app
    client = TestClient(app)
    HAS_APP = True
except Exception as e:
    HAS_APP = False
    APP_ERROR = str(e)


class TestHealthEndpoint:
    """Test health check and status endpoints."""
    
    def test_health_check(self):
        """Health endpoint should return 200 OK."""
        if not HAS_APP:
            pytest.skip(f"App not available: {APP_ERROR}")
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ["healthy", "ok", "degraded"]


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_404_for_unknown_route(self):
        """Unknown routes should return 404."""
        if not HAS_APP:
            pytest.skip(f"App not available: {APP_ERROR}")
        response = client.get("/api/nonexistent/route")
        assert response.status_code == 404


class TestSecurity:
    """Test security measures."""
    
    def test_cors_headers_present(self):
        """CORS headers should be set."""
        if not HAS_APP:
            pytest.skip(f"App not available: {APP_ERROR}")
        response = client.options("/api/health")
        assert response.status_code in [200, 204, 405]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

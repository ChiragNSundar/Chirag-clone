"""
Tests for the AI Clone Bot backend.
Run with: python -m pytest tests/ -v
"""
import pytest
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthCheck:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test that health check returns healthy status."""
        response = client.get('/api/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert 'service' in data


class TestChatEndpoints:
    """Test chat-related endpoints."""
    
    def test_chat_message_requires_message(self, client):
        """Test that chat endpoint requires a message."""
        response = client.post('/api/chat/message', 
                               json={},
                               content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_chat_message_rejects_empty(self, client):
        """Test that chat endpoint rejects empty messages."""
        response = client.post('/api/chat/message',
                               json={'message': '   '},
                               content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_chat_message_with_valid_input(self, client):
        """Test that chat endpoint accepts valid messages."""
        response = client.post('/api/chat/message',
                               json={'message': 'Hello!'},
                               content_type='application/json')
        # Should return 200 even with errors (friendly error messages)
        assert response.status_code == 200
        data = json.loads(response.data)
        # Should have either response or error
        assert 'response' in data or 'error' in data
    
    def test_new_session(self, client):
        """Test creating a new session."""
        response = client.post('/api/chat/new-session')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'session_id' in data
        assert len(data['session_id']) > 0
    
    def test_get_personality(self, client):
        """Test getting personality profile."""
        response = client.get('/api/chat/personality')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'name' in data


class TestTrainingEndpoints:
    """Test training-related endpoints."""
    
    def test_add_example_requires_fields(self, client):
        """Test that add example requires both fields."""
        response = client.post('/api/training/example',
                               json={'context': 'hello'},
                               content_type='application/json')
        assert response.status_code == 400
        
        response = client.post('/api/training/example',
                               json={'response': 'hi'},
                               content_type='application/json')
        assert response.status_code == 400
    
    def test_add_example_success(self, client):
        """Test successfully adding an example."""
        response = client.post('/api/training/example',
                               json={
                                   'context': 'Test context',
                                   'response': 'Test response'
                               },
                               content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('success') == True
    
    def test_add_fact_requires_fact(self, client):
        """Test that add fact requires a fact."""
        response = client.post('/api/training/fact',
                               json={},
                               content_type='application/json')
        assert response.status_code == 400
    
    def test_add_fact_success(self, client):
        """Test successfully adding a fact."""
        response = client.post('/api/training/fact',
                               json={'fact': 'I like testing'},
                               content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('success') == True
    
    def test_get_facts(self, client):
        """Test getting facts."""
        response = client.get('/api/training/facts')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'facts' in data
    
    def test_get_training_stats(self, client):
        """Test getting training stats."""
        response = client.get('/api/training/stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'total_examples' in data
    
    def test_feedback_requires_context(self, client):
        """Test that feedback requires context."""
        response = client.post('/api/training/feedback',
                               json={'accepted': True},
                               content_type='application/json')
        assert response.status_code == 400


class TestUploadEndpoints:
    """Test upload-related endpoints (basic validation only)."""
    
    def test_whatsapp_upload_no_file(self, client):
        """Test WhatsApp upload without file."""
        response = client.post('/api/upload/whatsapp',
                               data={'your_name': 'Test'},
                               content_type='multipart/form-data')
        # Should fail gracefully
        assert response.status_code in [400, 500]


class TestLLMService:
    """Test LLM service functionality."""
    
    def test_llm_service_initialization(self):
        """Test that LLM service initializes without crashing."""
        from services.llm_service import get_llm_service
        service = get_llm_service()
        assert service is not None
        assert service.provider is not None
    
    def test_llm_service_returns_response(self):
        """Test that LLM service returns some response (even error message)."""
        from services.llm_service import get_llm_service
        service = get_llm_service()
        response = service.generate_response(
            system_prompt="You are a test bot.",
            messages=[{"role": "user", "content": "Hello"}]
        )
        # Should return a string (either real response or error message)
        assert isinstance(response, str)
        assert len(response) > 0


class TestPersonalityService:
    """Test personality service functionality."""
    
    def test_personality_service_loads(self):
        """Test that personality service loads."""
        from services.personality_service import get_personality_service
        service = get_personality_service()
        assert service is not None
    
    def test_get_profile(self):
        """Test getting personality profile."""
        from services.personality_service import get_personality_service
        service = get_personality_service()
        profile = service.get_profile()
        assert profile is not None
        assert hasattr(profile, 'name')
        assert hasattr(profile, 'facts')
    
    def test_get_system_prompt(self):
        """Test getting system prompt."""
        from services.personality_service import get_personality_service
        service = get_personality_service()
        prompt = service.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestMemoryService:
    """Test memory service functionality."""
    
    def test_memory_service_loads(self):
        """Test that memory service loads."""
        from services.memory_service import get_memory_service
        service = get_memory_service()
        assert service is not None
    
    def test_get_training_stats(self):
        """Test getting training stats."""
        from services.memory_service import get_memory_service
        service = get_memory_service()
        stats = service.get_training_stats()
        assert isinstance(stats, dict)
        assert 'total_examples' in stats


class TestInputValidation:
    """Test input validation and error handling."""
    
    def test_chat_rejects_long_message(self, client):
        """Test that chat rejects messages over length limit."""
        # Create a message longer than 10000 characters
        long_message = "x" * 15000
        response = client.post('/api/chat/message',
                               json={'message': long_message},
                               content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'too long' in data['error'].lower()
    
    def test_chat_rejects_invalid_session_id(self, client):
        """Test that chat rejects invalid session IDs."""
        response = client.post('/api/chat/message',
                               json={
                                   'message': 'Hello',
                                   'session_id': 'invalid;session;id'
                               },
                               content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_training_rejects_long_context(self, client):
        """Test that training rejects long context."""
        long_context = "x" * 10000
        response = client.post('/api/training/example',
                               json={
                                   'context': long_context,
                                   'response': 'test'
                               },
                               content_type='application/json')
        assert response.status_code == 400
    
    def test_training_rejects_long_fact(self, client):
        """Test that training rejects long facts."""
        long_fact = "x" * 1000
        response = client.post('/api/training/fact',
                               json={'fact': long_fact},
                               content_type='application/json')
        assert response.status_code == 400
    
    def test_name_update_rejects_long_name(self, client):
        """Test that name update rejects long names."""
        response = client.put('/api/chat/personality/name',
                             json={'name': 'x' * 100},
                             content_type='application/json')
        assert response.status_code == 400


class TestSecurityHeaders:
    """Test security headers on responses."""
    
    def test_security_headers_present(self, client):
        """Test that security headers are present on responses."""
        response = client.get('/api/health')
        
        assert 'X-Content-Type-Options' in response.headers
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        
        assert 'X-Frame-Options' in response.headers
        assert response.headers['X-Frame-Options'] == 'DENY'
        
        assert 'X-XSS-Protection' in response.headers


class TestEnhancedHealthCheck:
    """Test enhanced health check endpoint."""
    
    def test_health_check_includes_checks(self, client):
        """Test that health check includes dependency checks."""
        response = client.get('/api/health')
        data = json.loads(response.data)
        
        assert 'checks' in data
        assert 'chromadb' in data['checks']
        assert 'llm' in data['checks']
        assert 'filesystem' in data['checks']
    
    def test_health_check_status_field(self, client):
        """Test that health check includes status field."""
        response = client.get('/api/health')
        data = json.loads(response.data)
        
        assert 'status' in data
        assert data['status'] in ['healthy', 'degraded']


class TestErrorHandling:
    """Test error handling and graceful failures."""
    
    def test_404_returns_json(self, client):
        """Test that 404 errors return JSON."""
        response = client.get('/api/nonexistent')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_invalid_json_handled(self, client):
        """Test that invalid JSON is handled gracefully."""
        response = client.post('/api/chat/message',
                               data='not valid json',
                               content_type='application/json')
        assert response.status_code == 400
    
    def test_upload_without_file_handled(self, client):
        """Test that upload without file is handled."""
        response = client.post('/api/upload/whatsapp',
                               data={'your_name': 'Test'})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data


class TestRateLimitHeaders:
    """Test rate limit headers on responses."""
    
    def test_rate_limit_headers_present(self, client):
        """Test that rate limit headers are present."""
        response = client.post('/api/chat/new-session')
        
        # Rate limit headers should be present
        assert 'X-RateLimit-Limit' in response.headers
        assert 'X-RateLimit-Remaining' in response.headers


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

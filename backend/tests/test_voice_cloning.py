
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from services.voice_cloning_service import VoiceCloningService
from main import app
import os

client = TestClient(app)

@pytest.fixture
def mock_elevenlabs_modules():
    """
    Mock the functions imported from 'elevenlabs' inside voice_cloning_service.py
    Since the service does `from elevenlabs import clone, ...`, we must patch
    `services.voice_cloning_service.clone` etc.
    """
    with patch('services.voice_cloning_service.HAS_ELEVENLABS', True):
        with patch('services.voice_cloning_service.clone', create=True) as mock_clone, \
             patch('services.voice_cloning_service.voices', create=True) as mock_voices, \
             patch('services.voice_cloning_service.delete', create=True) as mock_delete, \
             patch('services.voice_cloning_service.set_api_key', create=True):
             
            yield {
                'clone': mock_clone,
                'voices': mock_voices,
                'delete': mock_delete
            }

@pytest.fixture
def service(mock_elevenlabs_modules):
    # We patch os.environ BEFORE creating the service instance
    with patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'fake-key'}):
        svc = VoiceCloningService()
        return svc

def test_clone_voice_success(service, mock_elevenlabs_modules):
    # Setup mock return object
    mock_voice = MagicMock()
    mock_voice.voice_id = "new-id"
    mock_voice.name = "My Clone"
    mock_voice.category = "cloned"
    
    mock_elevenlabs_modules['clone'].return_value = mock_voice
    
    # Test
    with patch('os.path.exists', return_value=True):
        result = service.clone_voice("My Clone", "Desc", ["/path/to/audio.mp3"])
    
    assert result['status'] == 'success'
    assert result['voice_id'] == "new-id"
    mock_elevenlabs_modules['clone'].assert_called_once()

def test_get_cloned_voices(service, mock_elevenlabs_modules):
    # Setup
    v1 = MagicMock(voice_id="v1", name="Voice 1", category="premade", labels={})
    v2 = MagicMock(voice_id="v2", name="Voice 2", category="cloned", labels={})
    mock_elevenlabs_modules['voices'].return_value = [v1, v2]
    
    # Test
    result = service.get_cloned_voices()
    
    # Check
    assert len(result) == 2
    assert result[1]['category'] == 'cloned'

def test_delete_voice(service, mock_elevenlabs_modules):
    service.delete_voice("v1")
    mock_elevenlabs_modules['delete'].assert_called_once_with("v1")

# ============ API Security Tests ============

def test_api_delete_voice_unauthorized():
    # Attempt delete without header
    response = client.delete("/api/voice/some-id")
    assert response.status_code == 401
    assert "Training PIN required" in response.json()['detail']

def test_api_delete_voice_authorized():
    # Mock the service to return True for delete
    with patch('routes.voice._get_voice_cloning_service') as mock_get:
        mock_svc = MagicMock()
        mock_svc.delete_voice.return_value = True
        mock_get.return_value = mock_svc
        
        # Patch the PIN env var to match what we send
        with patch.dict(os.environ, {'TRAINING_PIN': '1234'}):
            # We must also patch where the router READS the env var from if it's at module level
            # In voice.py: TRAINING_PIN = os.environ.get(...)
            # Since module is already imported, we might need to patch the variable directly in the module
            with patch('routes.voice.TRAINING_PIN', '1234'):
                response = client.delete(
                    "/api/voice/some-id", 
                    headers={"X-Training-PIN": "1234"}
                )
                assert response.status_code == 200
                assert response.json()['success'] is True

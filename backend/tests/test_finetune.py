
import pytest
from unittest.mock import patch, MagicMock
from services.finetune_service import FineTuneService
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Mock the get_service functions that FineTuneService calls in __init__
@pytest.fixture
def mock_dependencies():
    with patch('services.finetune_service.get_memory_service') as mock_mem, \
         patch('services.finetune_service.get_personality_service') as mock_pers:
        
        # Setup Memory Mock
        mock_mem_instance = MagicMock()
        mock_mem_instance.get_all_examples_with_metadata.return_value = [
            {"context": "Hello", "response": "Hi there!"},
        ]
        mock_mem.return_value = mock_mem_instance
        
        # Setup Personality Mock
        mock_pers_instance = MagicMock()
        mock_profile = MagicMock()
        mock_profile.response_examples = [MagicMock(context="Ctx", response="Res")]
        mock_pers_instance.get_profile.return_value = mock_profile
        mock_pers_instance.get_system_prompt.return_value = "System Prompt"
        mock_pers.return_value = mock_pers_instance
        
        yield mock_mem_instance, mock_pers_instance

@pytest.fixture
def service(mock_dependencies):
    # Now we can instantiate without args, as it calls the mocked get_ functions
    return FineTuneService()

def test_get_dataset_stats(service):
    stats = service.get_dataset_stats()
    assert stats['training_examples'] == 1
    assert stats['personality_examples'] == 1
    assert stats['total_rows'] == 2

def test_export_dataset_creation(service):
    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        path = service.export_dataset(format="chatml")
        assert "finetune_dataset.jsonl" in path
        mock_open.assert_called()
        # For a context manager mock, the file handle is returned by __enter__
        handle = mock_open.return_value.__enter__.return_value
        assert handle.write.called

def test_api_stats_endpoint():
    # Patch the service getter used by the endpoint
    with patch('routes.finetune.get_finetune_service') as mock_get:
        mock_service = MagicMock()
        mock_service.get_dataset_stats.return_value = {"total_rows": 99}
        mock_get.return_value = mock_service
        
        response = client.get("/api/finetune/stats")
        assert response.status_code == 200
        assert response.json()['total_rows'] == 99

def test_api_export_endpoint():
    with patch('routes.finetune.get_finetune_service') as mock_get:
        mock_service = MagicMock()
        mock_service.export_dataset.return_value = "/tmp/fake.jsonl"
        mock_get.return_value = mock_service
        
        response = client.post("/api/finetune/export", json={"format": "chatml"})
        assert response.status_code == 200
        # The API returns {"status": "success", "path": ..., "message": ...}
        assert response.json()['path'] == "/tmp/fake.jsonl"

"""
conftest.py - Pytest configuration and shared fixtures.
Provides common test utilities across all test modules.
"""
import pytest
import sys
import os

# Add backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def test_client():
    """Create a test client for FastAPI app."""
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture
def mock_llm_response():
    """Provide a mock LLM response."""
    return (
        "Hello! I'm here to help.",
        0.9,
        {"primary": "friendly", "energy": 0.8}
    )


@pytest.fixture
def sample_chat_message():
    """Provide a sample chat message payload."""
    return {
        "message": "Hello!",
        "session_id": "test-session",
        "training_mode": False
    }


@pytest.fixture
def sample_training_feedback():
    """Provide sample training feedback."""
    return {
        "context": "What is your name?",
        "correct_response": "I'm Chirag!",
        "bot_response": "I'm an AI assistant.",
        "accepted": False
    }


@pytest.fixture
def sample_whatsapp_export():
    """Provide sample WhatsApp export content."""
    return """12/25/24, 10:30 AM - John: Hello everyone!
12/25/24, 10:31 AM - Jane: Hi John!
12/25/24, 10:32 AM - John: How are you doing?"""


@pytest.fixture
def sample_discord_export():
    """Provide sample Discord JSON export."""
    return {
        "messages": [
            {
                "author": {"name": "TestUser"},
                "content": "Hello Discord!",
                "timestamp": "2024-12-25T10:30:00.000Z"
            },
            {
                "author": {"name": "TestUser2"},
                "content": "Hey there!",
                "timestamp": "2024-12-25T10:31:00.000Z"
            }
        ]
    }


# Skip markers for different test categories
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "voice: marks tests as voice-related")
    config.addinivalue_line("markers", "vision: marks tests as vision-related")
    config.addinivalue_line("markers", "knowledge: marks tests as knowledge/brain station related")


@pytest.fixture
def sample_base64_image():
    """Provide a minimal 1x1 PNG image as base64."""
    return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


@pytest.fixture
def sample_knowledge_document():
    """Provide sample knowledge document for testing."""
    return {
        "content": "Python is a high-level programming language. It was created by Guido van Rossum.",
        "title": "Python Facts",
        "source": "test"
    }


@pytest.fixture
def sample_voice_text():
    """Provide sample text for voice synthesis."""
    return "Hello, this is a test of the voice synthesis system."


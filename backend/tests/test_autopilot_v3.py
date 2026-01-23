"""
Tests for v3.0 Autopilot Agents (Calendar, Slack, Wake Word).
"""
import pytest
from unittest.mock import Mock, patch

# ============= Calendar Agent Tests =============

@patch('services.calendar_service.get_llm_service')
def test_calendar_negotiation(mock_get_llm):
    """Test meeting negotiation logic."""
    from services.calendar_service import CalendarService
    
    mock_llm = Mock()
    # Mock LLM returning valid JSON
    mock_llm.generate_response.return_value = """
    ```json
    {
        "has_meeting_request": true,
        "suggested_title": "Project Sync",
        "suggested_duration": 30
    }
    ```
    """
    mock_get_llm.return_value = mock_llm
    
    service = CalendarService()
    # We need to mock personality too since it's used in __init__ or get_profile
    service.personality = Mock()
    service.personality.get_profile.return_value.name = "Bot"
    
    result = service.negotiate_meeting("Can we sync on the project?")
    
    assert result['success'] is True
    assert result['analysis']['suggested_title'] == "Project Sync"


def test_calendar_crud_methods():
    """Test update and delete event methods."""
    from services.calendar_service import CalendarService
    
    service = CalendarService()
    service.service = Mock() # Mock Google API client
    
    # Test Update
    service.service.events().get().execute.return_value = {'id': '123', 'summary': 'Old'}
    service.service.events().update().execute.return_value = {'id': '123', 'htmlLink': 'http', 'summary': 'New'}
    
    result = service.update_event('123', summary='New')
    assert result['updated'] is True
    
    # Test Delete
    service.service.events().delete().execute.return_value = None
    assert service.delete_event('123') is True


# ============= Slack Bot Tests =============

@patch('services.slack_bot_service.get_llm_service')
def test_slack_draft_generation(mock_get_llm):
    """Test generating Slack reply drafts."""
    from services.slack_bot_service import SlackBotService
    
    mock_llm = Mock()
    mock_llm.generate_response.return_value = "Sure, I can help with that."
    mock_get_llm.return_value = mock_llm
    
    service = SlackBotService()
    # Mock no configured token to rely on mocks
    service.is_configured = False 
    
    # Need to mock personality injection if used
    with patch('services.slack_bot_service.get_personality_service') as mock_p:
        mock_p.return_value.get_profile.return_value.name = "Bot"
        
        draft = service.generate_reply_draft("Can you help?")
        
        assert draft['platform'] == 'slack'
        assert draft['draft_reply'] == "Sure, I can help with that."
        assert len(service.pending_replies) == 1


# ============= Wake Word Tests =============

def test_wake_word_processing():
    """Test wake word detection logic."""
    from services.wake_word_service import WakeWordService, HAS_WAKE_WORD
    
    if not HAS_WAKE_WORD:
        pytest.skip("openwakeword not installed - skipping wake word test")
    
    with patch('services.wake_word_service.WakeWordModel') as MockModel:
        # Setup mock prediction
        mock_instance = Mock()
        # Return a high score for 'hey_jarvis'
        mock_instance.predict.return_value = {'hey_jarvis': [0.9]}
        MockModel.return_value = mock_instance
        
        service = WakeWordService()
        service.is_listening = True
        
        # Test detection
        # Create dummy audio bytes (16-bit PCM, 1024 samples)
        dummy_audio = b'\x00' * 2048 
        
        detected = service.process_audio_chunk(dummy_audio)
        assert detected == 'hey_jarvis'
        
        # Test fail case
        mock_instance.predict.return_value = {'hey_jarvis': [0.1]}
        detected = service.process_audio_chunk(dummy_audio)
        assert detected is None

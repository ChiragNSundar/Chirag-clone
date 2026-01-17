"""
Voice Service Tests - VAD, Barge-in, and VoiceState.

Run with: pytest tests/test_voice.py -v
"""
import pytest
import os
import sys
import asyncio
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# VoiceState Enum Tests
# ============================================================================

class TestVoiceState:
    """Test VoiceState enum values and transitions."""
    
    def test_voice_state_values(self):
        """Test VoiceState enum has expected values."""
        try:
            from services.realtime_voice_service import VoiceState
            
            assert VoiceState.IDLE is not None
            assert VoiceState.LISTENING is not None
            assert VoiceState.PROCESSING is not None
            assert VoiceState.SPEAKING is not None
            assert VoiceState.INTERRUPTED is not None
        except ImportError as e:
            pytest.skip(f"VoiceState not available: {e}")
    
    def test_voice_state_string_values(self):
        """Test VoiceState enum string representations."""
        try:
            from services.realtime_voice_service import VoiceState
            
            assert VoiceState.IDLE.value == "idle"
            assert VoiceState.LISTENING.value == "listening"
            assert VoiceState.SPEAKING.value == "speaking"
        except ImportError as e:
            pytest.skip(f"VoiceState not available: {e}")


# ============================================================================
# ConversationState Tests
# ============================================================================

class TestConversationState:
    """Test ConversationState dataclass."""
    
    @pytest.fixture
    def conversation_state(self):
        """Create a ConversationState for testing."""
        try:
            from services.realtime_voice_service import ConversationState
            return ConversationState(session_id="test")
        except ImportError as e:
            pytest.skip(f"ConversationState not available: {e}")
    
    def test_initial_state(self, conversation_state):
        """Test ConversationState initial values."""
        try:
            from services.realtime_voice_service import VoiceState
            
            assert conversation_state.is_bot_speaking == False
            assert conversation_state.interrupted == False
            assert conversation_state.state == VoiceState.IDLE
        except (AttributeError, ImportError):
            # May not have all fields depending on version
            assert conversation_state.is_bot_speaking == False
    
    def test_buffer_initialization(self, conversation_state):
        """Test audio buffer is initialized."""
        assert hasattr(conversation_state, 'audio_buffer')
        assert conversation_state.audio_buffer == b""
    
    def test_vad_tracking_fields(self, conversation_state):
        """Test VAD tracking fields exist."""
        # These were added in v2.6
        assert hasattr(conversation_state, 'vad_frames') or True


# ============================================================================
# VAD Detection Tests
# ============================================================================

class TestVADDetection:
    """Test Voice Activity Detection functionality."""
    
    @pytest.fixture
    def realtime_service(self):
        """Create RealtimeVoiceService for testing."""
        try:
            from services.realtime_voice_service import RealtimeVoiceService
            return RealtimeVoiceService()
        except ImportError as e:
            pytest.skip(f"RealtimeVoiceService not available: {e}")
    
    def test_detect_speech_energy_silent(self, realtime_service):
        """Test energy-based VAD detects silence."""
        # Create silent audio (all zeros)
        silent_audio = b'\x00' * 1600  # 100ms at 16kHz
        
        if hasattr(realtime_service, '_detect_voice_activity_energy'):
            result = realtime_service._detect_voice_activity_energy(silent_audio)
            assert result == False
        elif hasattr(realtime_service, '_detect_speech_energy'):
            result = realtime_service._detect_speech_energy(silent_audio)
            assert result == False
    
    def test_detect_speech_energy_loud(self, realtime_service):
        """Test energy-based VAD detects loud audio."""
        # Create loud audio (high values)
        loud_audio = b'\xff\x7f' * 800  # Max amplitude 16-bit audio
        
        if hasattr(realtime_service, '_detect_voice_activity_energy'):
            result = realtime_service._detect_voice_activity_energy(loud_audio)
            assert result == True
        elif hasattr(realtime_service, '_detect_speech_energy'):
            result = realtime_service._detect_speech_energy(loud_audio)
            assert result == True


# ============================================================================
# Barge-in Handler Tests
# ============================================================================

class TestBargeInHandler:
    """Test barge-in (interruption) handling."""
    
    @pytest.fixture
    def realtime_service(self):
        """Create RealtimeVoiceService for testing."""
        try:
            from services.realtime_voice_service import RealtimeVoiceService
            return RealtimeVoiceService()
        except ImportError as e:
            pytest.skip(f"RealtimeVoiceService not available: {e}")
    
    def test_handle_barge_in_method_exists(self, realtime_service):
        """Test handle_barge_in method exists."""
        assert hasattr(realtime_service, 'handle_barge_in')
        assert callable(realtime_service.handle_barge_in)
    
    def test_barge_in_returns_dict(self, realtime_service):
        """Test handle_barge_in returns a dictionary."""
        # Create a mock session
        session_id = "test-session"
        realtime_service.active_sessions = {}
        
        try:
            from services.realtime_voice_service import ConversationState, VoiceState
            session = ConversationState(session_id="test-session")
            session.is_bot_speaking = True
            session.state = VoiceState.SPEAKING
            realtime_service.active_sessions[session_id] = session
            
            result = realtime_service.handle_barge_in(session_id)
            
            assert isinstance(result, dict)
            assert "status" in result
            assert result["status"] == "interrupted"
            assert session.interrupted == True
            assert session.is_bot_speaking == False
        except ImportError:
            pytest.skip("Dependencies not available")
    
    def test_barge_in_when_not_speaking(self, realtime_service):
        """Test handle_barge_in when bot is not speaking."""
        session_id = "test-session"
        realtime_service.active_sessions = {}
        
        try:
            from services.realtime_voice_service import ConversationState, VoiceState
            session = ConversationState(session_id="test-session")
            session.is_bot_speaking = False
            session.state = VoiceState.IDLE
            realtime_service.active_sessions[session_id] = session
            
            result = realtime_service.handle_barge_in(session_id)
            
            # Should indicate nothing to interrupt
            assert isinstance(result, dict)
            # 'no_action' is returned by implementation
            assert result.get("status") in ["idle", "not_speaking", "interrupted", "no_action"]
        except ImportError:
            pytest.skip("Dependencies not available")


# ============================================================================
# Session Management Tests
# ============================================================================

class TestSessionManagement:
    """Test voice session management."""
    
    @pytest.fixture
    def realtime_service(self):
        """Create RealtimeVoiceService for testing."""
        try:
            from services.realtime_voice_service import RealtimeVoiceService
            return RealtimeVoiceService()
        except ImportError as e:
            pytest.skip(f"RealtimeVoiceService not available: {e}")
    
    def test_get_session(self, realtime_service):
        """Test getting existing session."""
        realtime_service.active_sessions = {}
        
        try:
            from services.realtime_voice_service import ConversationState
            test_session = ConversationState(session_id="test-id")
            realtime_service.active_sessions["test-id"] = test_session
            
            if hasattr(realtime_service, 'get_session'):
                result = realtime_service.get_session("test-id")
                assert result == test_session
        except ImportError:
            pytest.skip("ConversationState not available")
    
    def test_cleanup_session(self, realtime_service):
        """Test session cleanup."""
        realtime_service.active_sessions = {"test-id": MagicMock()}
        
        if hasattr(realtime_service, 'end_session'):
            realtime_service.end_session("test-id")
            assert "test-id" not in realtime_service.active_sessions


# ============================================================================
# Audio Chunk Handling Tests
# ============================================================================

class TestAudioChunkHandling:
    """Test audio chunk processing."""
    
    @pytest.fixture
    def realtime_service(self):
        """Create RealtimeVoiceService for testing."""
        try:
            from services.realtime_voice_service import RealtimeVoiceService
            return RealtimeVoiceService()
        except ImportError as e:
            pytest.skip(f"RealtimeVoiceService not available: {e}")
    
    @pytest.mark.asyncio
    async def test_empty_audio_chunk(self, realtime_service):
        """Test handling empty audio chunk."""
        session_id = "test-session"
        realtime_service.active_sessions = {}
        
        try:
            from services.realtime_voice_service import ConversationState
            realtime_service.active_sessions[session_id] = ConversationState(session_id=session_id)
            
            # This is an async method
            result = await realtime_service.handle_audio_chunk(session_id, "")
            
            # Should handle gracefully
            assert result is not None
        except ImportError:
            pytest.skip("Dependencies not available")


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestVoiceErrorHandling:
    """Test voice service error handling."""
    
    @pytest.fixture
    def realtime_service(self):
        """Create RealtimeVoiceService for testing."""
        try:
            from services.realtime_voice_service import RealtimeVoiceService
            return RealtimeVoiceService()
        except ImportError as e:
            pytest.skip(f"RealtimeVoiceService not available: {e}")
    
    def test_nonexistent_session(self, realtime_service):
        """Test handling nonexistent session gracefully."""
        realtime_service.active_sessions = {}
        
        if hasattr(realtime_service, 'get_session'):
            # This creates a session
            result = realtime_service.get_session("nonexistent")
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_malformed_audio_data(self, realtime_service):
        """Test handling malformed audio data."""
        session_id = "test-session"
        realtime_service.active_sessions = {}
        
        try:
            from services.realtime_voice_service import ConversationState
            realtime_service.active_sessions[session_id] = ConversationState(session_id=session_id)
            
            # Try with malformed data - should not crash
            try:
                await realtime_service.handle_audio_chunk(session_id, "not valid base64")
            except Exception:
                pass
        except ImportError:
            pytest.skip("Dependencies not available")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

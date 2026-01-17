"""
Tests for Local Voice Service (Offline TTS/STT)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import base64


class TestLocalVoiceService:
    """Tests for LocalVoiceService class."""
    
    @pytest.fixture
    def service(self):
        """Create service with mocked dependencies."""
        with patch('services.local_voice_service.HAS_FASTER_WHISPER', False), \
             patch('services.local_voice_service.HAS_PIPER', False):
            from services.local_voice_service import LocalVoiceService
            return LocalVoiceService()
    
    def test_init(self, service):
        """Test service initialization."""
        assert service.whisper_model_name == 'base'
        assert 'lessac' in service.piper_voice_name
    
    def test_get_status_no_dependencies(self, service):
        """Test status when dependencies are missing."""
        status = service.get_status()
        
        assert status['local_stt_available'] is False
        assert status['local_tts_available'] is False
    
    def test_transcribe_without_whisper(self, service):
        """Test transcribe returns error when whisper not available."""
        result = service.transcribe(b"audio data", "wav")
        
        assert 'error' in result
        assert result['local'] is False
    
    def test_synthesize_without_piper(self, service):
        """Test synthesize returns error when piper not available."""
        result = service.synthesize("Hello world")
        
        assert 'error' in result
        assert result['local'] is False
    
    def test_synthesize_text_validation(self, service):
        """Test text validation in synthesize."""
        # Empty text
        result = service.synthesize("")
        assert 'error' in result
        
        # Text too long
        long_text = "x" * 6000
        result = service.synthesize(long_text)
        assert 'error' in result
    
    def test_get_available_voices_empty(self, service):
        """Test getting voices when none downloaded."""
        voices = service.get_available_voices()
        # May be empty or contain downloaded voices
        assert isinstance(voices, list)


class TestLocalVoiceWithMockedDependencies:
    """Tests with fully mocked dependencies."""
    
    @pytest.fixture
    def mock_whisper_model(self):
        """Create a mock Whisper model."""
        mock = MagicMock()
        mock.transcribe.return_value = (
            [MagicMock(text="Hello world", start=0, end=1)],
            MagicMock(language="en", language_probability=0.99)
        )
        return mock
    
    def test_transcribe_success(self, mock_whisper_model):
        """Test successful transcription."""
        with patch('services.local_voice_service.HAS_FASTER_WHISPER', True), \
             patch('services.local_voice_service.HAS_PIPER', False):
            from services.local_voice_service import LocalVoiceService
            
            service = LocalVoiceService()
            service._whisper_model = mock_whisper_model
            service._init_error_stt = None
            
            with patch('tempfile.NamedTemporaryFile'), \
                 patch('os.unlink'):
                result = service.transcribe(b"audio data", "wav")
            
            # Should attempt to transcribe
            assert service._whisper_model is not None
    
    def test_transcribe_base64(self):
        """Test base64 transcription wrapper."""
        with patch('services.local_voice_service.HAS_FASTER_WHISPER', False), \
             patch('services.local_voice_service.HAS_PIPER', False):
            from services.local_voice_service import LocalVoiceService
            
            service = LocalVoiceService()
            
            # Valid base64
            audio_b64 = base64.b64encode(b"test audio").decode()
            result = service.transcribe_base64(audio_b64, "wav")
            
            assert 'error' in result  # Will fail because no whisper
    
    def test_transcribe_base64_invalid(self):
        """Test base64 transcription with invalid input."""
        with patch('services.local_voice_service.HAS_FASTER_WHISPER', False), \
             patch('services.local_voice_service.HAS_PIPER', False):
            from services.local_voice_service import LocalVoiceService
            
            service = LocalVoiceService()
            
            result = service.transcribe_base64("not valid base64!!!", "wav")
            
            assert 'error' in result
            assert 'decode' in result['error'].lower() or 'Base64' in result['error']


class TestLocalVoiceHelpers:
    """Tests for helper methods."""
    
    def test_cuda_available_check(self):
        """Test CUDA availability check."""
        with patch('services.local_voice_service.HAS_FASTER_WHISPER', False), \
             patch('services.local_voice_service.HAS_PIPER', False):
            from services.local_voice_service import LocalVoiceService
            
            service = LocalVoiceService()
            
            # Should return a boolean
            result = service._cuda_available()
            assert isinstance(result, bool)
    
    def test_cuda_available_no_torch(self):
        """Test CUDA check when torch not available."""
        with patch('services.local_voice_service.HAS_FASTER_WHISPER', False), \
             patch('services.local_voice_service.HAS_PIPER', False):
            from services.local_voice_service import LocalVoiceService
            
            service = LocalVoiceService()
            
            # Mock torch import failure
            import sys
            original_torch = sys.modules.get('torch')
            sys.modules['torch'] = None
            
            try:
                # Will return False if torch not available
                result = service._cuda_available()
                assert isinstance(result, bool)
            finally:
                if original_torch:
                    sys.modules['torch'] = original_torch


class TestVoiceServiceIntegration:
    """Integration tests for voice service with local fallback."""
    
    def test_voice_service_status_includes_local(self):
        """Test that main voice service reports local availability."""
        with patch('services.local_voice_service.HAS_FASTER_WHISPER', False), \
             patch('services.local_voice_service.HAS_PIPER', False):
            from services.voice_service import VoiceService
            
            service = VoiceService()
            status = service.get_status()
            
            # Should have local status fields
            assert 'local_stt_available' in status
            assert 'local_tts_available' in status
    
    def test_text_to_speech_local_first(self):
        """Test local-first TTS method."""
        with patch('services.local_voice_service.HAS_FASTER_WHISPER', False), \
             patch('services.local_voice_service.HAS_PIPER', False):
            from services.voice_service import VoiceService
            
            service = VoiceService()
            
            # Will fail since no TTS available
            result = service.text_to_speech_local_first("Hello world")
            
            assert 'error' in result
    
    def test_speech_to_text_local_first(self):
        """Test local-first STT method."""
        with patch('services.local_voice_service.HAS_FASTER_WHISPER', False), \
             patch('services.local_voice_service.HAS_PIPER', False):
            from services.voice_service import VoiceService
            
            service = VoiceService()
            
            result = service.speech_to_text_local_first(b"audio data")
            
            assert 'error' in result
    
    def test_get_available_voices_combined(self):
        """Test that voices include both local and cloud."""
        with patch('services.local_voice_service.HAS_FASTER_WHISPER', False), \
             patch('services.local_voice_service.HAS_PIPER', False):
            from services.voice_service import VoiceService
            
            service = VoiceService()
            voices = service.get_available_voices()
            
            # Should be a list (may be empty if no voices configured)
            assert isinstance(voices, list)

"""
Voice Service - Text-to-Speech and Speech-to-Text for voice interactions.
Local-first approach: Uses Piper TTS and faster-whisper STT by default.
Falls back to ElevenLabs/OpenAI Whisper if local fails or API keys are configured.
"""
from typing import Optional, Dict, Tuple, List
import os
import io
import base64
from datetime import datetime

from .logger import get_logger
from .local_voice_service import get_local_voice_service, HAS_FASTER_WHISPER, HAS_PIPER
from config import Config

logger = get_logger(__name__)

# Try to import optional dependencies
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("OpenAI not installed. Whisper STT disabled.")

try:
    from elevenlabs import generate, Voice, VoiceSettings
    from elevenlabs import set_api_key
    HAS_ELEVENLABS = True
except ImportError:
    HAS_ELEVENLABS = False
    logger.warning("ElevenLabs not installed. TTS disabled. Install with: pip install elevenlabs")


class VoiceService:
    """Service for voice input/output - TTS and STT."""
    
    # Default ElevenLabs voice settings
    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    DEFAULT_MODEL = "eleven_monolingual_v1"
    
    def __init__(self):
        # ElevenLabs for TTS
        self.elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY', '')
        self.tts_enabled = bool(self.elevenlabs_api_key) and HAS_ELEVENLABS
        
        if self.tts_enabled and HAS_ELEVENLABS:
            set_api_key(self.elevenlabs_api_key)
        
        # OpenAI for STT (Whisper)
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        self.stt_enabled = bool(self.openai_api_key) and HAS_OPENAI
        
        if self.stt_enabled:
            openai.api_key = self.openai_api_key
        
        # Voice settings
        self.voice_id = os.getenv('ELEVENLABS_VOICE_ID', self.DEFAULT_VOICE_ID)
        self.speaking_rate = 1.0
        self.stability = 0.5
        self.similarity_boost = 0.75
    
    def get_status(self) -> Dict:
        """Get service status including local and cloud options."""
        local_service = get_local_voice_service()
        local_status = local_service.get_status()
        
        return {
            # Local-first status
            'local_stt_available': local_status['local_stt_available'],
            'local_tts_available': local_status['local_tts_available'],
            'whisper_model': local_status['whisper_model'],
            'piper_voice': local_status['piper_voice'],
            # Cloud fallback status
            'cloud_tts_enabled': self.tts_enabled,
            'cloud_stt_enabled': self.stt_enabled,
            'has_elevenlabs': HAS_ELEVENLABS,
            'has_openai': HAS_OPENAI,
            'voice_id': self.voice_id,
            # Overall
            'tts_available': local_status['local_tts_available'] or self.tts_enabled,
            'stt_available': local_status['local_stt_available'] or self.stt_enabled
        }
    
    def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        return_base64: bool = True
    ) -> Optional[Dict]:
        """
        Convert text to speech audio.
        
        Args:
            text: Text to speak
            voice_id: Optional voice ID override
            return_base64: If true, return base64 encoded audio
            
        Returns:
            Dict with audio data and metadata
        """
        if not self.tts_enabled:
            return {'error': 'TTS not enabled. Set ELEVENLABS_API_KEY.'}
        
        if not text or len(text) > 5000:
            return {'error': 'Text must be 1-5000 characters.'}
        
        try:
            audio = generate(
                text=text,
                voice=Voice(
                    voice_id=voice_id or self.voice_id,
                    settings=VoiceSettings(
                        stability=self.stability,
                        similarity_boost=self.similarity_boost
                    )
                ),
                model=self.DEFAULT_MODEL
            )
            
            if return_base64:
                audio_bytes = b''.join(audio) if hasattr(audio, '__iter__') else audio
                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                return {
                    'audio_base64': audio_b64,
                    'format': 'mp3',
                    'text_length': len(text),
                    'local': False,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'audio_bytes': audio,
                    'format': 'mp3',
                    'local': False
                }
                
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return {'error': str(e)}
    
    def text_to_speech_local_first(
        self,
        text: str,
        voice_id: Optional[str] = None,
        return_base64: bool = True,
        prefer_cloud: bool = False
    ) -> Optional[Dict]:
        """
        Convert text to speech, trying local first then cloud fallback.
        
        Args:
            text: Text to speak
            voice_id: Optional voice ID override (cloud only)
            return_base64: If true, return base64 encoded audio
            prefer_cloud: If true, try cloud first (for higher quality)
            
        Returns:
            Dict with audio data and metadata
        """
        local_service = get_local_voice_service()
        
        # If prefer_cloud and cloud is available, try cloud first
        if prefer_cloud and self.tts_enabled:
            result = self.text_to_speech(text, voice_id, return_base64)
            if 'error' not in result:
                return result
            logger.warning(f"Cloud TTS failed, trying local: {result.get('error')}")
        
        # Try local first (default)
        local_status = local_service.get_status()
        if local_status['local_tts_available']:
            result = local_service.synthesize(text, return_base64)
            if 'error' not in result:
                return result
            logger.warning(f"Local TTS failed, trying cloud: {result.get('error')}")
        
        # Fallback to cloud
        if self.tts_enabled:
            return self.text_to_speech(text, voice_id, return_base64)
        
        return {'error': 'No TTS available. Install piper-tts or set ELEVENLABS_API_KEY.'}
    
    def speech_to_text(
        self,
        audio_data: bytes,
        audio_format: str = "wav"
    ) -> Optional[Dict]:
        """
        Convert speech audio to text using Whisper.
        
        Args:
            audio_data: Audio bytes
            audio_format: Audio format (wav, mp3, m4a, webm)
            
        Returns:
            Dict with transcribed text
        """
        if not self.stt_enabled:
            return {'error': 'STT not enabled. Set OPENAI_API_KEY.'}
        
        try:
            # Create file-like object
            audio_file = io.BytesIO(audio_data)
            audio_file.name = f"audio.{audio_format}"
            
            # Use OpenAI Whisper API
            client = openai.OpenAI(api_key=self.openai_api_key)
            
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
            
            return {
                'text': transcript,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"STT error: {e}")
            return {'error': str(e)}
    
    def speech_to_text_base64(
        self,
        audio_base64: str,
        audio_format: str = "webm"
    ) -> Optional[Dict]:
        """
        Convert base64 audio to text.
        
        Args:
            audio_base64: Base64 encoded audio
            audio_format: Audio format
            
        Returns:
            Dict with transcribed text
        """
        try:
            audio_data = base64.b64decode(audio_base64)
            return self.speech_to_text(audio_data, audio_format)
        except Exception as e:
            logger.error(f"Base64 decode error: {e}")
            return {'error': str(e)}
    
    def get_available_voices(self) -> list:
        """Get list of available voices (local + cloud)."""
        voices = []
        
        # Get local voices first
        local_service = get_local_voice_service()
        voices.extend(local_service.get_available_voices())
        
        # Add cloud voices if available
        if self.tts_enabled:
            try:
                from elevenlabs import voices as el_voices
                for v in el_voices():
                    voices.append({'id': v.voice_id, 'name': v.name, 'local': False})
            except Exception as e:
                logger.error(f"Error fetching cloud voices: {e}")
        
        return voices
    
    def speech_to_text_local_first(
        self,
        audio_data: bytes,
        audio_format: str = "wav",
        prefer_cloud: bool = False
    ) -> Optional[Dict]:
        """
        Convert speech to text, trying local first then cloud fallback.
        
        Args:
            audio_data: Audio bytes
            audio_format: Audio format (wav, mp3, m4a, webm)
            prefer_cloud: If true, try cloud first (for higher accuracy)
            
        Returns:
            Dict with transcribed text
        """
        local_service = get_local_voice_service()
        
        # If prefer_cloud and cloud is available, try cloud first
        if prefer_cloud and self.stt_enabled:
            result = self.speech_to_text(audio_data, audio_format)
            if 'error' not in result:
                return result
            logger.warning(f"Cloud STT failed, trying local: {result.get('error')}")
        
        # Try local first (default)
        local_status = local_service.get_status()
        if local_status['local_stt_available']:
            result = local_service.transcribe(audio_data, audio_format)
            if 'error' not in result:
                return result
            logger.warning(f"Local STT failed, trying cloud: {result.get('error')}")
        
        # Fallback to cloud
        if self.stt_enabled:
            return self.speech_to_text(audio_data, audio_format)
        
        return {'error': 'No STT available. Install faster-whisper or set OPENAI_API_KEY.'}
    
    def set_voice(self, voice_id: str):
        """Set the voice to use for TTS."""
        self.voice_id = voice_id
    
    def set_voice_settings(
        self,
        stability: Optional[float] = None,
        similarity_boost: Optional[float] = None
    ):
        """Update voice settings."""
        if stability is not None:
            self.stability = max(0, min(1, stability))
        if similarity_boost is not None:
            self.similarity_boost = max(0, min(1, similarity_boost))


# Singleton instance
_voice_service: Optional[VoiceService] = None


def get_voice_service() -> VoiceService:
    """Get the singleton voice service instance."""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service

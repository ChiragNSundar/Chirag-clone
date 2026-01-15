"""
Voice Service - Text-to-Speech and Speech-to-Text for voice interactions.
Supports ElevenLabs for TTS and OpenAI Whisper for STT.
"""
from typing import Optional, Dict, Tuple
import os
import io
import base64
from datetime import datetime

from .logger import get_logger
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
        """Get service status."""
        return {
            'tts_enabled': self.tts_enabled,
            'stt_enabled': self.stt_enabled,
            'has_elevenlabs': HAS_ELEVENLABS,
            'has_openai': HAS_OPENAI,
            'voice_id': self.voice_id
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
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'audio_bytes': audio,
                    'format': 'mp3'
                }
                
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return {'error': str(e)}
    
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
        """Get list of available ElevenLabs voices."""
        if not self.tts_enabled:
            return []
        
        try:
            from elevenlabs import voices
            return [{'id': v.voice_id, 'name': v.name} for v in voices()]
        except Exception as e:
            logger.error(f"Error fetching voices: {e}")
            return []
    
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

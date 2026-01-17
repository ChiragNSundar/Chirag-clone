"""
Local Voice Service - Offline-first TTS and STT using Piper and Faster-Whisper.
Falls back to cloud APIs (ElevenLabs/OpenAI) if configured and local fails.
"""
import os
import io
import base64
import wave
import tempfile
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime

from .logger import get_logger
from config import Config

logger = get_logger(__name__)

# ============= Dependency Detection =============

HAS_FASTER_WHISPER = False
HAS_PIPER = False

try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    logger.info("faster-whisper not installed. Local STT will be disabled.")

try:
    from piper import PiperVoice
    HAS_PIPER = True
except ImportError:
    logger.info("piper-tts not installed. Local TTS will be disabled.")


class LocalVoiceService:
    """
    Offline-first voice service using local models.
    - STT: faster-whisper (Whisper via CTranslate2)
    - TTS: Piper (lightweight neural TTS)
    """
    
    # Model configurations
    WHISPER_MODELS = ['tiny', 'base', 'small', 'medium', 'large-v2']
    DEFAULT_WHISPER_MODEL = 'base'
    
    # Piper voice paths (auto-downloaded on first use)
    PIPER_VOICES_DIR = Path(__file__).parent.parent / 'data' / 'piper_voices'
    DEFAULT_PIPER_VOICE = 'en_US-lessac-medium'
    
    def __init__(self):
        self._whisper_model = None
        self._piper_voice = None
        self._init_error_stt = None
        self._init_error_tts = None
        
        # Model settings from config or defaults
        self.whisper_model_name = getattr(Config, 'LOCAL_WHISPER_MODEL', self.DEFAULT_WHISPER_MODEL)
        self.piper_voice_name = getattr(Config, 'LOCAL_PIPER_VOICE', self.DEFAULT_PIPER_VOICE)
        
        # Ensure voices directory exists
        self.PIPER_VOICES_DIR.mkdir(parents=True, exist_ok=True)
    
    # ============= STT (Speech-to-Text) =============
    
    def _init_whisper(self):
        """Lazy initialization of Whisper model."""
        if self._whisper_model is not None or self._init_error_stt:
            return
        
        if not HAS_FASTER_WHISPER:
            self._init_error_stt = "faster-whisper not installed"
            return
        
        try:
            # Auto-detect device: CUDA if available, else CPU
            device = "cuda" if self._cuda_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            
            logger.info(f"Loading Whisper model '{self.whisper_model_name}' on {device}...")
            self._whisper_model = WhisperModel(
                self.whisper_model_name,
                device=device,
                compute_type=compute_type
            )
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            self._init_error_stt = str(e)
            logger.error(f"Failed to load Whisper: {e}")
    
    def _cuda_available(self) -> bool:
        """Check if CUDA is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def transcribe(
        self,
        audio_data: bytes,
        audio_format: str = "wav",
        language: Optional[str] = None
    ) -> Dict:
        """
        Transcribe audio to text using local Whisper model.
        
        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format (wav, mp3, webm, etc.)
            language: Optional language code (e.g., 'en', 'es')
            
        Returns:
            Dict with 'text', 'language', 'segments', and 'confidence'
        """
        self._init_whisper()
        
        if self._init_error_stt:
            return {'error': self._init_error_stt, 'local': False}
        
        try:
            # Write audio to temp file (faster-whisper needs file path)
            with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            try:
                # Transcribe
                segments, info = self._whisper_model.transcribe(
                    temp_path,
                    language=language,
                    beam_size=5,
                    vad_filter=True  # Filter out non-speech
                )
                
                # Collect results
                text_parts = []
                all_segments = []
                for segment in segments:
                    text_parts.append(segment.text)
                    all_segments.append({
                        'start': segment.start,
                        'end': segment.end,
                        'text': segment.text.strip()
                    })
                
                full_text = ' '.join(text_parts).strip()
                
                return {
                    'text': full_text,
                    'language': info.language,
                    'language_probability': info.language_probability,
                    'segments': all_segments,
                    'local': True,
                    'timestamp': datetime.now().isoformat()
                }
            finally:
                # Cleanup temp file
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"Local STT error: {e}")
            return {'error': str(e), 'local': True}
    
    def transcribe_base64(
        self,
        audio_base64: str,
        audio_format: str = "webm",
        language: Optional[str] = None
    ) -> Dict:
        """Transcribe base64-encoded audio."""
        try:
            audio_data = base64.b64decode(audio_base64)
            return self.transcribe(audio_data, audio_format, language)
        except Exception as e:
            return {'error': f"Base64 decode failed: {e}", 'local': True}
    
    # ============= TTS (Text-to-Speech) =============
    
    def _init_piper(self):
        """Lazy initialization of Piper TTS."""
        if self._piper_voice is not None or self._init_error_tts:
            return
        
        if not HAS_PIPER:
            self._init_error_tts = "piper-tts not installed"
            return
        
        try:
            voice_path = self.PIPER_VOICES_DIR / f"{self.piper_voice_name}.onnx"
            config_path = self.PIPER_VOICES_DIR / f"{self.piper_voice_name}.onnx.json"
            
            # Check if voice exists, if not download it
            if not voice_path.exists():
                logger.info(f"Downloading Piper voice '{self.piper_voice_name}'...")
                self._download_piper_voice(self.piper_voice_name)
            
            logger.info(f"Loading Piper voice '{self.piper_voice_name}'...")
            self._piper_voice = PiperVoice.load(str(voice_path), str(config_path))
            logger.info("Piper voice loaded successfully")
            
        except Exception as e:
            self._init_error_tts = str(e)
            logger.error(f"Failed to load Piper: {e}")
    
    def _download_piper_voice(self, voice_name: str):
        """Download a Piper voice model."""
        import urllib.request
        
        base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
        lang_code = voice_name.split('-')[0]  # e.g., 'en_US' from 'en_US-lessac-medium'
        
        for ext in ['.onnx', '.onnx.json']:
            url = f"{base_url}/{lang_code}/{voice_name}/{voice_name}{ext}"
            dest = self.PIPER_VOICES_DIR / f"{voice_name}{ext}"
            
            logger.info(f"Downloading {url}...")
            urllib.request.urlretrieve(url, dest)
        
        logger.info(f"Downloaded Piper voice: {voice_name}")
    
    def synthesize(
        self,
        text: str,
        return_base64: bool = True,
        speed: float = 1.0
    ) -> Dict:
        """
        Synthesize speech from text using local Piper TTS.
        
        Args:
            text: Text to speak
            return_base64: If True, return base64-encoded audio
            speed: Speech rate multiplier (0.5 = half speed, 2.0 = double speed)
            
        Returns:
            Dict with 'audio_base64' or 'audio_bytes', 'format', etc.
        """
        self._init_piper()
        
        if self._init_error_tts:
            return {'error': self._init_error_tts, 'local': False}
        
        if not text or len(text) > 5000:
            return {'error': 'Text must be 1-5000 characters', 'local': True}
        
        try:
            # Synthesize to WAV in memory
            audio_buffer = io.BytesIO()
            
            with wave.open(audio_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(22050)
                
                # Generate audio
                for audio_bytes in self._piper_voice.synthesize_stream_raw(text):
                    wav_file.writeframes(audio_bytes)
            
            audio_buffer.seek(0)
            audio_data = audio_buffer.read()
            
            if return_base64:
                return {
                    'audio_base64': base64.b64encode(audio_data).decode('utf-8'),
                    'format': 'wav',
                    'text_length': len(text),
                    'local': True,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'audio_bytes': audio_data,
                    'format': 'wav',
                    'local': True
                }
                
        except Exception as e:
            logger.error(f"Local TTS error: {e}")
            return {'error': str(e), 'local': True}
    
    # ============= Status & Info =============
    
    def get_status(self) -> Dict:
        """Get service status including model info."""
        self._init_whisper()
        self._init_piper()
        
        return {
            'local_stt_available': HAS_FASTER_WHISPER and self._init_error_stt is None,
            'local_tts_available': HAS_PIPER and self._init_error_tts is None,
            'whisper_model': self.whisper_model_name if self._whisper_model else None,
            'piper_voice': self.piper_voice_name if self._piper_voice else None,
            'stt_error': self._init_error_stt,
            'tts_error': self._init_error_tts,
            'cuda_available': self._cuda_available()
        }
    
    def get_available_voices(self) -> List[Dict]:
        """List available Piper voices (downloaded ones)."""
        voices = []
        for f in self.PIPER_VOICES_DIR.glob("*.onnx"):
            voice_name = f.stem
            voices.append({
                'id': voice_name,
                'name': voice_name.replace('-', ' ').title(),
                'local': True
            })
        return voices


# ============= Singleton =============

_local_voice_service: Optional[LocalVoiceService] = None


def get_local_voice_service() -> LocalVoiceService:
    """Get the singleton local voice service instance."""
    global _local_voice_service
    if _local_voice_service is None:
        _local_voice_service = LocalVoiceService()
    return _local_voice_service

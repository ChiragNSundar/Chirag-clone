"""
Wake Word Service - Local wake word detection using openWakeWord.
Allows hands-free activation of voice chat.
"""
import os
import asyncio
from typing import Optional, Callable, Dict
from threading import Thread
import queue

from .logger import get_logger

logger = get_logger(__name__)

# Try to import openWakeWord
try:
    from openwakeword.model import Model as WakeWordModel
    HAS_WAKE_WORD = True
except ImportError:
    HAS_WAKE_WORD = False
    logger.warning("openwakeword not installed. Install with: pip install openwakeword")


class WakeWordService:
    """Service for local wake word detection."""
    
    # Built-in wake word models from openWakeWord
    AVAILABLE_MODELS = [
        'hey_jarvis',
        'alexa',
        'hey_mycroft',
        'ok_google'
    ]
    
    def __init__(self):
        self.is_configured = HAS_WAKE_WORD
        self.model = None
        self.is_listening = False
        self.wake_word = os.getenv('WAKE_WORD_MODEL', 'hey_jarvis')
        self.threshold = float(os.getenv('WAKE_WORD_THRESHOLD', '0.5'))
        self._audio_queue: queue.Queue = queue.Queue()
        self._callback: Optional[Callable] = None
        self._listener_thread: Optional[Thread] = None
        
        if HAS_WAKE_WORD:
            try:
                # Load the wake word model
                self.model = WakeWordModel(
                    wakeword_models=[self.wake_word],
                    inference_framework='onnx'
                )
                logger.info(f"✅ Wake word model loaded: {self.wake_word}")
            except Exception as e:
                logger.error(f"Wake word model load failed: {e}")
                self.is_configured = False
    
    def get_status(self) -> Dict:
        """Get service status."""
        return {
            'available': self.is_configured,
            'has_library': HAS_WAKE_WORD,
            'wake_word': self.wake_word,
            'is_listening': self.is_listening,
            'threshold': self.threshold,
            'available_models': self.AVAILABLE_MODELS
        }
    
    def set_wake_word(self, model_name: str) -> bool:
        """Change the active wake word model."""
        if not HAS_WAKE_WORD:
            return False
        
        if model_name not in self.AVAILABLE_MODELS:
            logger.warning(f"Unknown wake word model: {model_name}")
            return False
        
        try:
            self.model = WakeWordModel(
                wakeword_models=[model_name],
                inference_framework='onnx'
            )
            self.wake_word = model_name
            logger.info(f"Wake word changed to: {model_name}")
            return True
        except Exception as e:
            logger.error(f"Error changing wake word: {e}")
            return False
    
    def process_audio_chunk(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[str]:
        """
        Process an audio chunk and check for wake word.
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
            sample_rate: Audio sample rate (default 16kHz)
            
        Returns:
            Wake word name if detected, None otherwise
        """
        if not self.model or not self.is_listening:
            return None
        
        try:
            import numpy as np
            
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Normalize to float32 in range [-1, 1]
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # Run prediction
            prediction = self.model.predict(audio_float)
            
            # Check if any wake word exceeded threshold
            for model_name, scores in prediction.items():
                if len(scores) > 0 and max(scores) >= self.threshold:
                    logger.info(f"🎤 Wake word detected: {model_name} (confidence: {max(scores):.2f})")
                    return model_name
            
            return None
            
        except Exception as e:
            logger.error(f"Wake word processing error: {e}")
            return None
    
    def start_listening(self, on_wake_word: Optional[Callable] = None):
        """Start listening for wake word."""
        if not self.is_configured:
            logger.warning("Wake word not configured, cannot start listening")
            return False
        
        self.is_listening = True
        self._callback = on_wake_word
        
        logger.info(f"🎤 Started listening for wake word: '{self.wake_word}'")
        return True
    
    def stop_listening(self):
        """Stop listening for wake word."""
        self.is_listening = False
        self._callback = None
        logger.info("🔇 Stopped wake word listening")
    
    def add_audio_chunk(self, audio_data: bytes):
        """Add audio chunk to processing queue."""
        if self.is_listening:
            self._audio_queue.put(audio_data)
            
            # Process immediately
            detected = self.process_audio_chunk(audio_data)
            if detected and self._callback:
                self._callback(detected)
                return True
        
        return False


# Singleton instance
_wake_word_service: Optional[WakeWordService] = None


def get_wake_word_service() -> WakeWordService:
    """Get the singleton wake word service instance."""
    global _wake_word_service
    if _wake_word_service is None:
        _wake_word_service = WakeWordService()
    return _wake_word_service

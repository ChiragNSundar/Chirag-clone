"""
Voice Cloning Service - wrapper for ElevenLabs voice cloning API.
"""
from typing import Optional, List, Dict
import os
import io
import logging
from config import Config

logger = logging.getLogger(__name__)

# Try to import elevenlabs
try:
    from elevenlabs import clone, set_api_key, voices, delete
    HAS_ELEVENLABS = True
except ImportError:
    HAS_ELEVENLABS = False
    logger.warning("ElevenLabs not installed. Voice cloning disabled.")


class VoiceCloningService:
    """Service to manage voice cloning operations."""
    
    def __init__(self):
        self.api_key = os.getenv('ELEVENLABS_API_KEY', '')
        self.enabled = bool(self.api_key) and HAS_ELEVENLABS
        
        if self.enabled:
            try:
                set_api_key(self.api_key)
            except Exception as e:
                logger.error(f"Failed to set ElevenLabs API key: {e}")
                self.enabled = False
    
    def clone_voice(self, name: str, description: str, file_paths: List[str]) -> Dict:
        """
        Clone a voice from audio files.
        /!\ Can be expensive and limited by tier.
        
        Args:
            name: Name of the voice
            description: Description for the voice
            file_paths: List of absolute paths to audio files
            
        Returns:
            Dict containing the new voice object properties
        """
        if not self.enabled:
            return {'error': 'Voice cloning not enabled. Check API key and installation.'}
            
        if not file_paths:
            return {'error': 'No audio files provided.'}
            
        try:
            # Validate files exist
            valid_files = [f for f in file_paths if os.path.exists(f)]
            if not valid_files:
                return {'error': 'No valid audio files found.'}
                
            # Call ElevenLabs clone
            # Note: actual method signature depends on elevenlabs version. 
            # We assume modern version supporting list of file paths or bytes.
            new_voice = clone(
                name=name,
                description=description,
                files=valid_files
            )
            
            return {
                'voice_id': new_voice.voice_id,
                'name': new_voice.name,
                'category': new_voice.category,
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Voice cloning error: {e}")
            return {'error': str(e)}

    def get_cloned_voices(self) -> List[Dict]:
        """Get list of all voices including cloned ones."""
        if not self.enabled:
            return []
            
        try:
            all_voices = voices()
            # Filter or mark cloned voices (usually category is 'cloned')
            results = []
            for v in all_voices:
                results.append({
                    'voice_id': v.voice_id,
                    'name': v.name,
                    'category': v.category,
                    'labels': v.labels
                })
            return results
        except Exception as e:
            logger.error(f"Error fetching voices: {e}")
            return []
            
    def delete_voice(self, voice_id: str) -> bool:
        """Delete a voice by ID."""
        if not self.enabled:
            return False
            
        try:
            delete(voice_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting voice {voice_id}: {e}")
            return False

# Singleton
_service = None

def get_voice_cloning_service():
    global _service
    if not _service:
        _service = VoiceCloningService()
    return _service

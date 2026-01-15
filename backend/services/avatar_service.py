"""
Avatar Service - Text-to-viseme timing for 3D avatar lip-sync.
Provides phoneme mapping and timing data without TTS dependency.
"""
from typing import List, Dict, Optional
import re


# Phoneme to viseme mapping for Ready Player Me avatars
PHONEME_VISEME_MAP = {
    'a': 'viseme_aa',
    'e': 'viseme_E',
    'i': 'viseme_I',
    'o': 'viseme_O',
    'u': 'viseme_U',
    'b': 'viseme_PP',
    'm': 'viseme_PP',
    'p': 'viseme_PP',
    'f': 'viseme_FF',
    'v': 'viseme_FF',
    's': 'viseme_SS',
    'z': 'viseme_SS',
    't': 'viseme_TH',
    'th': 'viseme_TH',
    'd': 'viseme_DD',
    'n': 'viseme_nn',
    'l': 'viseme_nn',
    'r': 'viseme_RR',
    'k': 'viseme_kk',
    'g': 'viseme_kk',
    'ch': 'viseme_CH',
    'sh': 'viseme_CH',
}

# Default viseme durations in milliseconds
DEFAULT_PHONEME_DURATION = 60
DIGRAPH_DURATION = 80
WORD_GAP_DURATION = 100


class AvatarService:
    """Service for generating lip-sync data for 3D avatars."""
    
    def __init__(self):
        self.phoneme_map = PHONEME_VISEME_MAP
        self.speaking_speed = 1.0  # Adjustable speaking speed multiplier
    
    def text_to_visemes(self, text: str) -> List[Dict]:
        """
        Convert text to a sequence of viseme timings for lip-sync.
        
        Args:
            text: The text to convert to visemes
            
        Returns:
            List of dicts with 'viseme' and 'duration' keys
        """
        visemes = []
        words = text.lower().split()
        
        for word in words:
            # Clean word of punctuation
            clean_word = re.sub(r'[^\w]', '', word)
            chars = list(clean_word)
            
            i = 0
            while i < len(chars):
                char = chars[i]
                
                # Check for digraphs (two-character phonemes)
                if i + 1 < len(chars):
                    digraph = char + chars[i + 1]
                    if digraph in self.phoneme_map:
                        visemes.append({
                            'viseme': self.phoneme_map[digraph],
                            'duration': int(DIGRAPH_DURATION / self.speaking_speed)
                        })
                        i += 2
                        continue
                
                # Single character mapping
                if char in self.phoneme_map:
                    visemes.append({
                        'viseme': self.phoneme_map[char],
                        'duration': int(DEFAULT_PHONEME_DURATION / self.speaking_speed)
                    })
                
                i += 1
            
            # Add silence between words
            visemes.append({
                'viseme': 'viseme_sil',
                'duration': int(WORD_GAP_DURATION / self.speaking_speed)
            })
        
        return visemes
    
    def get_animation_duration(self, text: str) -> int:
        """
        Calculate the total duration for lip-sync animation.
        
        Args:
            text: The text being spoken
            
        Returns:
            Total duration in milliseconds
        """
        visemes = self.text_to_visemes(text)
        return sum(v['duration'] for v in visemes)
    
    def set_speaking_speed(self, speed: float):
        """
        Set the speaking speed multiplier.
        
        Args:
            speed: Speed multiplier (1.0 = normal, 2.0 = twice as fast)
        """
        self.speaking_speed = max(0.5, min(3.0, speed))
    
    def get_available_visemes(self) -> List[str]:
        """Get list of all available viseme names."""
        return list(set(self.phoneme_map.values())) + ['viseme_sil']


# Singleton instance
_avatar_service: Optional[AvatarService] = None


def get_avatar_service() -> AvatarService:
    """Get the singleton avatar service instance."""
    global _avatar_service
    if _avatar_service is None:
        _avatar_service = AvatarService()
    return _avatar_service

"""
Emotion Service - Detect emotions in user messages and adapt responses.
Uses LLM-based sentiment and emotion analysis.
"""
from typing import Dict, Optional, Tuple, List
from datetime import datetime
import re

from .llm_service import get_llm_service
from .logger import get_logger

logger = get_logger(__name__)


class EmotionService:
    """Service for detecting and responding to emotions in messages."""
    
    # Emotion categories with emojis
    EMOTIONS = {
        'happy': {'emoji': '😊', 'response_tone': 'match their positive energy'},
        'excited': {'emoji': '🎉', 'response_tone': 'be enthusiastic and supportive'},
        'grateful': {'emoji': '🙏', 'response_tone': 'be warm and appreciative'},
        'loving': {'emoji': '❤️', 'response_tone': 'be affectionate and caring'},
        'neutral': {'emoji': '😐', 'response_tone': 'be balanced and conversational'},
        'curious': {'emoji': '🤔', 'response_tone': 'be informative and engaging'},
        'confused': {'emoji': '😕', 'response_tone': 'be clear and helpful'},
        'sad': {'emoji': '😢', 'response_tone': 'be empathetic and supportive'},
        'frustrated': {'emoji': '😤', 'response_tone': 'be understanding and solution-focused'},
        'angry': {'emoji': '😠', 'response_tone': 'be calm and de-escalating'},
        'anxious': {'emoji': '😰', 'response_tone': 'be reassuring and calming'},
        'stressed': {'emoji': '😓', 'response_tone': 'be supportive and offer help'},
        'tired': {'emoji': '😴', 'response_tone': 'be gentle and concise'},
        'bored': {'emoji': '🥱', 'response_tone': 'be engaging and interesting'},
    }
    
    # Quick emotion keywords for fast detection
    EMOTION_KEYWORDS = {
        'happy': ['happy', 'glad', 'great', 'awesome', 'wonderful', 'amazing', 'love', 'yay', '!', ':)', '😊'],
        'excited': ['excited', 'can\'t wait', 'pumped', 'stoked', '!!!', 'omg', 'wow'],
        'sad': ['sad', 'upset', 'depressed', 'down', 'unhappy', 'crying', ':(', '😢'],
        'frustrated': ['frustrated', 'annoyed', 'ugh', 'irritating', 'hate', 'stupid'],
        'angry': ['angry', 'furious', 'mad', 'pissed', 'rage'],
        'anxious': ['anxious', 'worried', 'nervous', 'scared', 'afraid', 'panic'],
        'stressed': ['stressed', 'overwhelmed', 'too much', 'can\'t handle', 'exhausted'],
        'confused': ['confused', 'don\'t understand', 'what?', 'huh', 'lost', '?'],
        'curious': ['curious', 'wondering', 'how', 'why', 'what if', 'interested'],
        'grateful': ['thank', 'appreciate', 'grateful', 'thanks', '🙏'],
    }
    
    def __init__(self):
        self.llm = get_llm_service()
        self._emotion_history: List[Dict] = []
        self._max_history = 50
    
    def detect_emotion(self, message: str) -> Dict:
        """
        Detect the primary emotion in a message.
        Uses keyword matching first, then LLM for ambiguous cases.
        
        Returns:
            Dict with emotion, emoji, intensity, and response_tone
        """
        if not message:
            return self._get_emotion_data('neutral', 0.5)
        
        message_lower = message.lower()
        
        # Quick keyword matching
        keyword_scores = {}
        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            if score > 0:
                keyword_scores[emotion] = score
        
        if keyword_scores:
            # Use highest scoring emotion
            top_emotion = max(keyword_scores, key=keyword_scores.get)
            intensity = min(keyword_scores[top_emotion] / 3, 1.0)
            return self._get_emotion_data(top_emotion, intensity)
        
        # For longer messages, use LLM analysis
        if len(message.split()) > 5:
            return self._llm_detect_emotion(message)
        
        return self._get_emotion_data('neutral', 0.5)
    
    def _llm_detect_emotion(self, message: str) -> Dict:
        """Use LLM for nuanced emotion detection."""
        emotions_list = ', '.join(self.EMOTIONS.keys())
        
        prompt = f"""Analyze the emotional tone of this message and return ONLY the emotion name.
        
Available emotions: {emotions_list}

Message: "{message}"

Emotion (one word only):"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=20,
                temperature=0.3
            )
            
            # Parse response
            emotion = response.strip().lower().split()[0] if response else 'neutral'
            emotion = re.sub(r'[^a-z]', '', emotion)
            
            if emotion not in self.EMOTIONS:
                emotion = 'neutral'
            
            return self._get_emotion_data(emotion, 0.7)
            
        except Exception as e:
            logger.error(f"LLM emotion detection error: {e}")
            return self._get_emotion_data('neutral', 0.5)
    
    def _get_emotion_data(self, emotion: str, intensity: float) -> Dict:
        """Get full emotion data dict."""
        emotion_info = self.EMOTIONS.get(emotion, self.EMOTIONS['neutral'])
        
        data = {
            'emotion': emotion,
            'emoji': emotion_info['emoji'],
            'intensity': round(intensity, 2),
            'response_tone': emotion_info['response_tone'],
            'timestamp': datetime.now().isoformat()
        }
        
        # Track history
        self._emotion_history.append(data)
        if len(self._emotion_history) > self._max_history:
            self._emotion_history = self._emotion_history[-self._max_history:]
        
        return data
    
    def get_emotion_context_prompt(self, emotion_data: Dict) -> str:
        """Get a prompt injection for emotional context."""
        if not emotion_data or emotion_data.get('emotion') == 'neutral':
            return ""
        
        emotion = emotion_data.get('emotion', 'neutral')
        tone = emotion_data.get('response_tone', '')
        intensity = emotion_data.get('intensity', 0.5)
        
        if intensity < 0.3:
            return ""
        
        return f"\n\nEMOTIONAL CONTEXT: The user seems {emotion}. {tone.capitalize()}."
    
    def get_emotion_history(self, limit: int = 10) -> List[Dict]:
        """Get recent emotion history."""
        return self._emotion_history[-limit:]
    
    def get_dominant_emotion(self) -> Optional[str]:
        """Get the most common recent emotion."""
        if not self._emotion_history:
            return None
        
        recent = self._emotion_history[-10:]
        emotions = [e['emotion'] for e in recent]
        
        from collections import Counter
        counter = Counter(emotions)
        return counter.most_common(1)[0][0]
    
    def get_emotion_stats(self) -> Dict:
        """Get emotion statistics."""
        if not self._emotion_history:
            return {'total': 0, 'distribution': {}}
        
        from collections import Counter
        emotions = [e['emotion'] for e in self._emotion_history]
        counter = Counter(emotions)
        
        total = len(emotions)
        distribution = {e: round(c / total * 100, 1) for e, c in counter.items()}
        
        return {
            'total': total,
            'distribution': distribution,
            'dominant': self.get_dominant_emotion()
        }


# Singleton instance
_emotion_service: Optional[EmotionService] = None


def get_emotion_service() -> EmotionService:
    """Get the singleton emotion service instance."""
    global _emotion_service
    if _emotion_service is None:
        _emotion_service = EmotionService()
    return _emotion_service

"""
Mood Service - Tracks and manages the bot's emotional state.
"""
from datetime import datetime
import random

class MoodService:
    """Service to track the bot's mood based on interactions and time."""
    
    MOODS = {
        'happy': {'emoji': '😊', 'prompt': 'You are in a great mood! Be enthusiastic, use emojis, and be helpful.'},
        'neutral': {'emoji': '😐', 'prompt': 'You are feeling normal. Be polite and conversational.'},
        'annoyed': {'emoji': '😒', 'prompt': 'You are slightly annoyed. Be brief, maybe a bit sarcastic, and less helpful.'},
        'tired': {'emoji': '🥱', 'prompt': 'You are tired. Respond slowly, maybe mention needing coffee or sleep. Be lazy.'},
        'excited': {'emoji': '🤩', 'prompt': 'You are super excited! Use exclamation marks! Be very high energy!'}
    }
    
    def __init__(self):
        self.current_mood = 'neutral'
        self.last_interaction = datetime.now()
        self.interaction_count = 0
    
    def get_mood(self):
        """Get the current mood."""
        self._update_mood_by_time()
        return {
            'mood': self.current_mood,
            'emoji': self.MOODS[self.current_mood]['emoji'],
            'prompt': self.MOODS[self.current_mood]['prompt']
        }
    
    def update_mood_from_interaction(self, user_message: str):
        """Update mood based on what the user said."""
        self.last_interaction = datetime.now()
        self.interaction_count += 1
        
        # Simple keywords to shift mood
        text = user_message.lower()
        
        if any(w in text for w in ['dumb', 'stupid', 'bad', 'hate', 'shut up']):
            self.current_mood = 'annoyed'
        elif any(w in text for w in ['love', 'great', 'awesome', 'cool', 'thanks']):
            if self.current_mood == 'annoyed':
                self.current_mood = 'neutral' # Forgive
            else:
                self.current_mood = 'happy'
        elif any(w in text for w in ['wow', 'amazing', 'omg', 'party']):
            self.current_mood = 'excited'
        elif self.interaction_count > 20: # Getting tired of talking
             if random.random() < 0.1:
                 self.current_mood = 'tired'
                 
        return self.get_mood()

    def _update_mood_by_time(self):
        """Check if time of day affects mood."""
        hour = datetime.now().hour
        
        # Late night -> Tired
        if hour >= 23 or hour < 6:
            if self.current_mood != 'excited': # Excitement overrides tiredness
                self.current_mood = 'tired'
        
        # Reset to neutral if it's been a while
        time_since = (datetime.now() - self.last_interaction).total_seconds()
        if time_since > 3600 and self.current_mood in ['annoyed', 'happy', 'excited']:
            self.current_mood = 'neutral'

# Singleton
_mood_service = None

def get_mood_service():
    global _mood_service
    if _mood_service is None:
        _mood_service = MoodService()
    return _mood_service

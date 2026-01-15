"""
Creative Service - Generate creative content in user's style.
Supports poems, stories, journal entries, and more.
"""
from typing import Dict, Optional, List
from datetime import datetime

from .llm_service import get_llm_service
from .personality_service import get_personality_service
from .logger import get_logger

logger = get_logger(__name__)


class CreativeService:
    """Service for generating creative content in user's style."""
    
    CONTENT_TYPES = {
        'poem': {
            'name': 'Poem',
            'prompt_template': 'Write a poem about {topic} in {name}\'s style.',
            'max_tokens': 500
        },
        'haiku': {
            'name': 'Haiku',
            'prompt_template': 'Write a haiku about {topic} in {name}\'s perspective.',
            'max_tokens': 100
        },
        'story': {
            'name': 'Short Story',
            'prompt_template': 'Write a short story about {topic} as {name} would tell it.',
            'max_tokens': 1000
        },
        'journal': {
            'name': 'Journal Entry',
            'prompt_template': 'Write a personal journal entry about {topic} as if you are {name}.',
            'max_tokens': 800
        },
        'dream': {
            'name': 'Dream Description',
            'prompt_template': 'Describe a vivid dream about {topic} from {name}\'s perspective.',
            'max_tokens': 600
        },
        'letter': {
            'name': 'Letter',
            'prompt_template': 'Write a heartfelt letter about {topic} in {name}\'s voice.',
            'max_tokens': 700
        },
        'reflection': {
            'name': 'Reflection',
            'prompt_template': 'Write a thoughtful reflection on {topic} as {name}.',
            'max_tokens': 600
        }
    }
    
    def __init__(self):
        self.llm = get_llm_service()
        self.personality = get_personality_service()
        self._generated: List[Dict] = []
    
    def generate(
        self,
        content_type: str,
        topic: str = "",
        custom_prompt: Optional[str] = None,
        style_intensity: float = 0.8
    ) -> Dict:
        """
        Generate creative content.
        
        Args:
            content_type: Type of content (poem, story, journal, etc.)
            topic: Topic to write about
            custom_prompt: Optional custom prompt override
            style_intensity: How strongly to apply user's style (0-1)
        """
        if content_type not in self.CONTENT_TYPES and not custom_prompt:
            return {'error': f'Unknown content type: {content_type}'}
        
        profile = self.personality.get_profile()
        
        # Build the prompt
        if custom_prompt:
            base_prompt = custom_prompt
            content_info = {'name': 'Custom', 'max_tokens': 800}
        else:
            content_info = self.CONTENT_TYPES[content_type]
            topic_text = topic if topic else "life and experiences"
            base_prompt = content_info['prompt_template'].format(
                topic=topic_text,
                name=profile.name
            )
        
        # Add personality context
        style_prompt = f"""You are {profile.name}, writing creatively.

PERSONALITY TRAITS:
- Tone: {', '.join(list(profile.tone_markers.keys())[:5])}
- Common phrases you use: {', '.join(profile.common_phrases[:5])}
- Your emojis: {', '.join(list(profile.emojis.keys())[:5])}
- Your quirks: {', '.join(profile.quirks[:3])}

STYLE INTENSITY: {style_intensity * 100:.0f}% (how strongly to reflect your unique voice)

TASK: {base_prompt}

Write authentically as yourself. Output ONLY the creative content, no explanations:"""

        try:
            response = self.llm.generate(
                prompt=style_prompt,
                max_tokens=content_info.get('max_tokens', 500),
                temperature=0.9  # Higher temperature for creativity
            )
            
            result = {
                'id': f"creative_{datetime.now().timestamp()}",
                'type': content_type,
                'topic': topic,
                'content': response.strip(),
                'created_at': datetime.now().isoformat(),
                'word_count': len(response.split())
            }
            
            self._generated.append(result)
            return result
            
        except Exception as e:
            logger.error(f"Creative generation error: {e}")
            return {'error': str(e)}
    
    def get_content_types(self) -> List[Dict]:
        """Get available content types."""
        return [
            {'id': k, 'name': v['name']}
            for k, v in self.CONTENT_TYPES.items()
        ]
    
    def get_recent_creations(self, limit: int = 10) -> List[Dict]:
        """Get recently generated creative content."""
        return self._generated[-limit:]
    
    def generate_daily_prompt(self) -> str:
        """Generate a creative writing prompt for the day."""
        prompts = [
            "Write about a childhood memory that shaped who you are",
            "Describe your perfect day from start to finish",
            "Write a letter to your past self",
            "Reflect on something you learned recently",
            "Describe a place that feels like home",
            "Write about a fear you've overcome",
            "Imagine meeting yourself 10 years from now",
            "Write about a moment of unexpected joy"
        ]
        
        # Use date to pick a consistent prompt
        day_of_year = datetime.now().timetuple().tm_yday
        return prompts[day_of_year % len(prompts)]


# Singleton instance
_creative_service: Optional[CreativeService] = None


def get_creative_service() -> CreativeService:
    """Get the singleton creative service instance."""
    global _creative_service
    if _creative_service is None:
        _creative_service = CreativeService()
    return _creative_service

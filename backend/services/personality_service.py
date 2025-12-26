"""
Personality Service - Extracts and manages personality profiles from chat data.
"""
import json
import re
from typing import List, Dict, Optional
from collections import Counter
from config import Config


class PersonalityProfile:
    """Represents a personality profile extracted from chat data."""
    
    def __init__(self):
        self.name = Config.BOT_NAME
        self.common_phrases: List[str] = []
        self.emoji_patterns: Dict[str, int] = {}
        self.vocabulary: Dict[str, int] = {}
        self.avg_message_length: float = 0
        self.typing_quirks: List[str] = []  # e.g., "lol", "bruh", "ngl"
        self.tone_markers: Dict[str, float] = {
            'casual': 0.5,
            'formal': 0.5,
            'sarcastic': 0.0,
            'enthusiastic': 0.5,
            'brief': 0.5
        }
        self.facts: List[str] = []  # Personal facts about the user
        self.response_examples: List[Dict[str, str]] = []
    
    def to_dict(self) -> dict:
        """Convert profile to dictionary."""
        return {
            'name': self.name,
            'common_phrases': self.common_phrases,
            'emoji_patterns': self.emoji_patterns,
            'vocabulary': dict(list(self.vocabulary.items())[:100]),  # Top 100 words
            'avg_message_length': self.avg_message_length,
            'typing_quirks': self.typing_quirks,
            'tone_markers': self.tone_markers,
            'facts': self.facts,
            'response_examples': self.response_examples[:20]  # Top 20 examples
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PersonalityProfile':
        """Create profile from dictionary."""
        profile = cls()
        profile.name = data.get('name', Config.BOT_NAME)
        profile.common_phrases = data.get('common_phrases', [])
        profile.emoji_patterns = data.get('emoji_patterns', {})
        profile.vocabulary = data.get('vocabulary', {})
        profile.avg_message_length = data.get('avg_message_length', 0)
        profile.typing_quirks = data.get('typing_quirks', [])
        profile.tone_markers = data.get('tone_markers', profile.tone_markers)
        profile.facts = data.get('facts', [])
        profile.response_examples = data.get('response_examples', [])
        return profile
    
    def to_prompt(self) -> str:
        """Convert personality to a system prompt."""
        prompt_parts = [
            f"You are {self.name}. You must respond EXACTLY as {self.name} would in a text conversation.",
            "",
            "PERSONALITY TRAITS:"
        ]
        
        # Tone description
        tone_desc = []
        if self.tone_markers.get('casual', 0) > 0.6:
            tone_desc.append("very casual and informal")
        if self.tone_markers.get('sarcastic', 0) > 0.4:
            tone_desc.append("sometimes sarcastic")
        if self.tone_markers.get('enthusiastic', 0) > 0.6:
            tone_desc.append("enthusiastic and energetic")
        if self.tone_markers.get('brief', 0) > 0.6:
            tone_desc.append("keeps messages short")
        
        if tone_desc:
            prompt_parts.append(f"- Communication style: {', '.join(tone_desc)}")
        
        # Typing quirks
        if self.typing_quirks:
            prompt_parts.append(f"- Common expressions: {', '.join(self.typing_quirks[:10])}")
        
        # Emoji usage
        if self.emoji_patterns:
            top_emojis = sorted(self.emoji_patterns.items(), key=lambda x: x[1], reverse=True)[:5]
            emoji_str = ' '.join([e[0] for e in top_emojis])
            prompt_parts.append(f"- Frequently uses these emojis: {emoji_str}")
        
        # Message length
        if self.avg_message_length > 0:
            if self.avg_message_length < 30:
                prompt_parts.append("- Sends short, quick messages")
            elif self.avg_message_length > 100:
                prompt_parts.append("- Often sends longer, detailed messages")
        
        # Personal facts
        if self.facts:
            prompt_parts.append("")
            prompt_parts.append("PERSONAL FACTS:")
            for fact in self.facts[:10]:
                prompt_parts.append(f"- {fact}")
        
        # Instructions
        prompt_parts.extend([
            "",
            "IMPORTANT RULES:",
            "- Respond naturally as if texting a friend",
            "- Use the exact typing style, slang, and expressions from the examples",
            "- Keep responses similar in length to the examples",
            "- Don't be overly helpful or formal - be authentic",
            "- Never break character or mention you're an AI"
        ])
        
        return "\n".join(prompt_parts)


class PersonalityService:
    """Service for managing personality profiles."""
    
    def __init__(self):
        self.profile = self._load_profile()
    
    def _load_profile(self) -> PersonalityProfile:
        """Load profile from file or create new one."""
        try:
            with open(Config.PERSONALITY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return PersonalityProfile.from_dict(data)
        except (FileNotFoundError, json.JSONDecodeError):
            return PersonalityProfile()
    
    def save_profile(self):
        """Save current profile to file."""
        with open(Config.PERSONALITY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.profile.to_dict(), f, indent=2, ensure_ascii=False)
    
    def analyze_messages(self, messages: List[str]) -> None:
        """
        Analyze a list of messages to extract personality traits.
        
        Args:
            messages: List of message strings from the user
        """
        if not messages:
            return
        
        # Message length analysis
        lengths = [len(m) for m in messages]
        self.profile.avg_message_length = sum(lengths) / len(lengths)
        
        # Vocabulary analysis
        all_words = []
        for msg in messages:
            words = re.findall(r'\b[a-zA-Z]+\b', msg.lower())
            all_words.extend(words)
        
        word_counts = Counter(all_words)
        self.profile.vocabulary = dict(word_counts.most_common(200))
        
        # Emoji analysis
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", 
            flags=re.UNICODE
        )
        
        all_emojis = []
        for msg in messages:
            emojis = emoji_pattern.findall(msg)
            all_emojis.extend(emojis)
        
        self.profile.emoji_patterns = dict(Counter(all_emojis).most_common(20))
        
        # Typing quirks detection
        quirk_patterns = [
            r'\blol\b', r'\blmao\b', r'\bromfl\b', r'\bhaha\b', r'\bhehe\b',
            r'\bbruh\b', r'\bbro\b', r'\bdude\b', r'\bman\b',
            r'\bngl\b', r'\btbh\b', r'\bidk\b', r'\bimo\b', r'\bbtw\b',
            r'\blike\b', r'\bliterally\b', r'\bbasically\b',
            r'\bok+\b', r'\byeah+\b', r'\bya+\b', r'\byep\b', r'\bnope\b',
            r'\bomg\b', r'\bwtf\b', r'\bwth\b',
            r'\bcool\b', r'\bnice\b', r'\bsick\b', r'\bdope\b',
            r'\.{2,}', r'!{2,}', r'\?{2,}'  # Multiple punctuation
        ]
        
        detected_quirks = []
        for pattern in quirk_patterns:
            matches = []
            for msg in messages:
                found = re.findall(pattern, msg.lower())
                matches.extend(found)
            if len(matches) > len(messages) * 0.05:  # Used in >5% of messages
                detected_quirks.append(matches[0] if matches else pattern.strip('\\b'))
        
        self.profile.typing_quirks = list(set(detected_quirks))[:15]
        
        # Tone analysis
        casual_indicators = ['lol', 'haha', 'gonna', 'wanna', 'kinda', 'ya', 'yep', 'nope', 'bruh']
        formal_indicators = ['would', 'could', 'please', 'thank you', 'regards', 'certainly']
        
        casual_count = sum(1 for msg in messages for ind in casual_indicators if ind in msg.lower())
        formal_count = sum(1 for msg in messages for ind in formal_indicators if ind in msg.lower())
        
        total = casual_count + formal_count + 1
        self.profile.tone_markers['casual'] = casual_count / total
        self.profile.tone_markers['formal'] = formal_count / total
        
        # Brief vs detailed
        self.profile.tone_markers['brief'] = 1.0 if self.profile.avg_message_length < 50 else 0.3
        
        self.save_profile()
    
    def add_example(self, context: str, response: str) -> None:
        """Add a response example to the profile."""
        self.profile.response_examples.append({
            'context': context,
            'response': response
        })
        self.save_profile()
    
    def add_fact(self, fact: str) -> None:
        """Add a personal fact to the profile."""
        if fact not in self.profile.facts:
            self.profile.facts.append(fact)
            self.save_profile()
    
    def update_name(self, name: str) -> None:
        """Update the personality name."""
        self.profile.name = name
        self.save_profile()
    
    def get_profile(self) -> PersonalityProfile:
        """Get the current personality profile."""
        return self.profile
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for the LLM."""
        return self.profile.to_prompt()


# Singleton instance
_personality_service = None

def get_personality_service() -> PersonalityService:
    """Get the singleton personality service instance."""
    global _personality_service
    if _personality_service is None:
        _personality_service = PersonalityService()
    return _personality_service

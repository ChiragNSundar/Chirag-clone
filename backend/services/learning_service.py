"""
Learning Service - Active learning from conversations.
Analyzes user messages, asks probing questions, and learns personality.
"""
import random
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import re


class LearningService:
    """Service for active learning from user conversations."""
    
    # Questions to understand user's personality and viewpoints
    DISCOVERY_QUESTIONS = [
        # Personality & Communication
        "btw, how would you describe your texting style? casual, formal, somewhere in between?",
        "do you prefer short quick messages or longer detailed ones?",
        "are you more of an emoji person or words person?",
        
        # Interests & Preferences
        "what do you usually spend your free time on?",
        "what topics could you talk about for hours?",
        "any pet peeves that really annoy you?",
        
        # Viewpoints & Values
        "what's something you feel strongly about?",
        "do you consider yourself more optimistic or realistic?",
        "what's the best advice you've ever received?",
        
        # Social & Relationships
        "how do you usually respond when friends vent to you?",
        "are you the advice-giving type or more of a listener?",
        "what makes someone a good friend in your opinion?",
        
        # Fun & Light
        "what's a random fact about yourself most people don't know?",
        "if you had to describe yourself in 3 words, what would they be?",
        "what's something that always makes you laugh?",
    ]
    
    # Patterns to detect in user messages for learning
    STYLE_INDICATORS = {
        'casual': [r'\blol\b', r'\bhaha\b', r'\bbruh\b', r'\bya\b', r'\byeah\b', r'\bngl\b', r'\btbh\b'],
        'enthusiastic': [r'!{2,}', r'so\s+\w+!', r'\bomg\b', r'\bamazing\b', r'\bawesome\b'],
        'brief': [],  # Detected by message length
        'uses_emojis': [r'[\U0001F600-\U0001F64F]', r'[\U0001F300-\U0001F5FF]'],
        'asks_questions': [r'\?'],
        'thoughtful': [r'\bi think\b', r'\bimo\b', r'\bpersonally\b', r'\bi feel\b'],
    }
    
    def __init__(self):
        self.questions_asked: List[str] = []
        self.interaction_count = 0
        self.last_question_at = 0
    
    def analyze_message(self, message: str) -> Dict:
        """
        Analyze a user message for style patterns.
        
        Returns dict with detected patterns and extracted info.
        """
        analysis = {
            'is_casual': False,
            'is_enthusiastic': False,
            'is_brief': len(message) < 50,
            'uses_emojis': False,
            'is_thoughtful': False,
            'word_count': len(message.split()),
            'has_slang': False,
            'sentiment': 'neutral'
        }
        
        msg_lower = message.lower()
        
        # Check style indicators
        for style, patterns in self.STYLE_INDICATORS.items():
            for pattern in patterns:
                if re.search(pattern, msg_lower if style != 'uses_emojis' else message):
                    if style == 'casual':
                        analysis['is_casual'] = True
                        analysis['has_slang'] = True
                    elif style == 'enthusiastic':
                        analysis['is_enthusiastic'] = True
                        analysis['sentiment'] = 'positive'
                    elif style == 'uses_emojis':
                        analysis['uses_emojis'] = True
                    elif style == 'thoughtful':
                        analysis['is_thoughtful'] = True
                    break
        
        return analysis
    
    def extract_facts_from_message(self, message: str) -> List[str]:
        """
        Extract potential personal facts from a user message.
        
        Looks for patterns like:
        - "I like/love/hate..."
        - "I'm a..."
        - "I work as..."
        - "My favorite..."
        """
        facts = []
        msg_lower = message.lower()
        
        fact_patterns = [
            (r"i(?:'m| am) (?:a |an )?(.+?)(?:\.|,|$)", "is {0}"),
            (r"i (?:really )?(?:love|like|enjoy) (.+?)(?:\.|,|$)", "loves {0}"),
            (r"i (?:really )?(?:hate|dislike|can't stand) (.+?)(?:\.|,|$)", "dislikes {0}"),
            (r"my favorite (\w+) is (.+?)(?:\.|,|$)", "favorite {0} is {1}"),
            (r"i work (?:as|in) (.+?)(?:\.|,|$)", "works as {0}"),
            (r"i(?:'m| am) from (.+?)(?:\.|,|$)", "from {0}"),
            (r"i (?:always|usually|often) (.+?)(?:\.|,|$)", "often {0}"),
        ]
        
        for pattern, template in fact_patterns:
            matches = re.findall(pattern, msg_lower)
            for match in matches:
                if isinstance(match, tuple):
                    fact = template.format(*match)
                else:
                    fact = template.format(match)
                if len(fact) > 5 and len(fact) < 100:  # Reasonable length
                    facts.append(fact.strip())
        
        return facts
    
    def should_ask_question(self) -> bool:
        """
        Decide if it's a good time to ask a discovery question.
        
        Rules:
        - Not too frequently (at least 5 interactions apart)
        - Randomly (30% chance when eligible)
        - Haven't asked all questions yet
        """
        self.interaction_count += 1
        
        # Need at least 5 interactions between questions
        if self.interaction_count - self.last_question_at < 5:
            return False
        
        # Have available questions
        available = [q for q in self.DISCOVERY_QUESTIONS if q not in self.questions_asked]
        if not available:
            return False
        
        # 25% chance to ask
        return random.random() < 0.25
    
    def get_discovery_question(self) -> Optional[str]:
        """Get a random discovery question that hasn't been asked yet."""
        available = [q for q in self.DISCOVERY_QUESTIONS if q not in self.questions_asked]
        
        if not available:
            return None
        
        question = random.choice(available)
        self.questions_asked.append(question)
        self.last_question_at = self.interaction_count
        
        return question
    
    def learn_from_exchange(
        self,
        user_message: str,
        bot_response: str,
        personality_service,
        memory_service
    ) -> Dict:
        """
        Learn from a conversation exchange.
        
        Args:
            user_message: What the user said
            bot_response: What the bot replied
            personality_service: Service to update personality
            memory_service: Service to store examples
            
        Returns:
            Dict with learning results
        """
        results = {
            'analyzed': True,
            'facts_extracted': [],
            'style_learned': [],
            'example_saved': False
        }
        
        # Analyze user's message style
        analysis = self.analyze_message(user_message)
        
        # Update personality based on patterns
        profile = personality_service.get_profile()
        
        if analysis['is_casual']:
            profile.tone_markers['casual'] = min(1.0, profile.tone_markers.get('casual', 0.5) + 0.05)
            results['style_learned'].append('casual')
        
        if analysis['is_brief']:
            profile.tone_markers['brief'] = min(1.0, profile.tone_markers.get('brief', 0.5) + 0.05)
            results['style_learned'].append('brief')
        
        if analysis['is_enthusiastic']:
            profile.tone_markers['enthusiastic'] = min(1.0, profile.tone_markers.get('enthusiastic', 0.5) + 0.05)
            results['style_learned'].append('enthusiastic')
        
        # Extract and save facts
        facts = self.extract_facts_from_message(user_message)
        for fact in facts:
            if fact not in profile.facts:
                personality_service.add_fact(fact)
                results['facts_extracted'].append(fact)
        
        # Save meaningful exchanges as training examples
        # (Only if message is substantial enough)
        if len(user_message) > 10:
            try:
                memory_service.add_training_example(
                    context=user_message,
                    response=bot_response,
                    source="auto_learned"
                )
                results['example_saved'] = True
            except:
                pass
        
        # Save personality updates
        if results['style_learned'] or results['facts_extracted']:
            personality_service.save_profile()
        
        return results


# Singleton instance
_learning_service = None

def get_learning_service() -> LearningService:
    """Get the singleton learning service instance."""
    global _learning_service
    if _learning_service is None:
        _learning_service = LearningService()
    return _learning_service

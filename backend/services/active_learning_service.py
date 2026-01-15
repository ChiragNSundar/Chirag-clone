"""
Active Learning Service - Proactive knowledge gap detection and question generation.
Detects gaps in the clone's knowledge and generates questions to fill them.
"""
from typing import List, Dict, Optional, Set
from datetime import datetime
import json
import re

from .llm_service import get_llm_service
from .memory_service import get_memory_service
from .personality_service import get_personality_service
from .logger import get_logger

logger = get_logger(__name__)


class ActiveLearningService:
    """Service for detecting knowledge gaps and generating proactive questions."""
    
    # Topics that a complete digital clone should know about
    KNOWLEDGE_DOMAINS = {
        'personal_basics': ['name', 'age', 'location', 'occupation', 'education'],
        'preferences': ['favorite_food', 'favorite_movie', 'favorite_music', 'hobbies'],
        'relationships': ['family', 'friends', 'romantic_status'],
        'personality': ['strengths', 'weaknesses', 'pet_peeves', 'values'],
        'lifestyle': ['morning_routine', 'exercise', 'sleep_habits', 'diet'],
        'opinions': ['politics', 'technology', 'social_issues'],
        'history': ['memorable_events', 'achievements', 'challenges'],
        'goals': ['short_term', 'long_term', 'bucket_list'],
    }
    
    # Question templates for each domain
    QUESTION_TEMPLATES = {
        'personal_basics': [
            "What's your current job or what do you do professionally?",
            "Where did you grow up?",
            "What's your educational background?",
        ],
        'preferences': [
            "I know we've talked about movies, but what's your all-time favorite?",
            "What kind of music do you listen to most?",
            "What are your main hobbies or things you do for fun?",
            "What's your go-to comfort food?",
        ],
        'relationships': [
            "Tell me about your closest friends or family members.",
            "Who has been most influential in your life?",
        ],
        'personality': [
            "What would you say are your biggest strengths?",
            "What's something that really annoys you?",
            "What values are most important to you?",
        ],
        'lifestyle': [
            "What does a typical day look like for you?",
            "How do you usually unwind after a long day?",
            "Are you a morning person or night owl?",
        ],
        'opinions': [
            "What's a topic you're really passionate about?",
            "What do you think about the future of AI?",
        ],
        'history': [
            "What's a memorable experience that shaped who you are?",
            "What's something you're proud of accomplishing?",
        ],
        'goals': [
            "What are you working towards right now?",
            "Is there something you've always wanted to do but haven't yet?",
        ],
    }
    
    def __init__(self):
        self.llm = get_llm_service()
        self.memory = get_memory_service()
        self.personality = get_personality_service()
        
        # Track asked questions to avoid repetition
        self._asked_questions: Set[str] = set()
        self._answered_domains: Set[str] = set()
    
    def detect_knowledge_gaps(self) -> Dict[str, float]:
        """
        Analyze existing knowledge to find gaps.
        
        Returns:
            Dict mapping domain to coverage score (0-1)
        """
        try:
            profile = self.personality.get_profile()
            facts = profile.facts if hasattr(profile, 'facts') else []
            
            # Get all training examples
            examples = self.memory.get_all_examples_with_metadata(limit=500)
            
            # Combine all known text
            knowledge_text = " ".join(facts)
            if examples:
                for ex in examples:
                    knowledge_text += " " + ex.get('content', '') + " " + ex.get('response', '')
            
            knowledge_lower = knowledge_text.lower()
            
            # Score each domain
            domain_scores = {}
            for domain, keywords in self.KNOWLEDGE_DOMAINS.items():
                matches = sum(1 for kw in keywords if kw.replace('_', ' ') in knowledge_lower)
                coverage = min(matches / len(keywords), 1.0)
                domain_scores[domain] = coverage
            
            return domain_scores
            
        except Exception as e:
            logger.error(f"Error detecting knowledge gaps: {e}")
            return {}
    
    def generate_proactive_questions(
        self,
        max_questions: int = 3
    ) -> List[Dict]:
        """
        Generate proactive questions to fill knowledge gaps.
        
        Args:
            max_questions: Maximum number of questions to generate
            
        Returns:
            List of question dicts with 'question' and 'domain' keys
        """
        try:
            gaps = self.detect_knowledge_gaps()
            
            # Sort domains by gap size (lowest coverage first)
            sorted_domains = sorted(gaps.items(), key=lambda x: x[1])
            
            questions = []
            for domain, coverage in sorted_domains:
                if len(questions) >= max_questions:
                    break
                
                # Skip if domain is well covered
                if coverage >= 0.7:
                    continue
                
                # Skip if domain was recently addressed
                if domain in self._answered_domains:
                    continue
                
                # Get templates for this domain
                templates = self.QUESTION_TEMPLATES.get(domain, [])
                
                for template in templates:
                    # Skip if already asked
                    if template in self._asked_questions:
                        continue
                    
                    questions.append({
                        'question': template,
                        'domain': domain,
                        'coverage': coverage,
                        'priority': self._calculate_priority(domain, coverage)
                    })
                    self._asked_questions.add(template)
                    break  # One question per domain
            
            # Sort by priority
            questions.sort(key=lambda x: x['priority'], reverse=True)
            
            return questions[:max_questions]
            
        except Exception as e:
            logger.error(f"Error generating proactive questions: {e}")
            return []
    
    def _calculate_priority(self, domain: str, coverage: float) -> float:
        """Calculate priority score for a question."""
        # Base priority on how low the coverage is
        gap_priority = 1.0 - coverage
        
        # Boost priority for fundamental domains
        domain_weights = {
            'personal_basics': 1.5,
            'preferences': 1.3,
            'personality': 1.2,
            'relationships': 1.0,
            'lifestyle': 0.9,
            'goals': 1.0,
            'history': 0.8,
            'opinions': 0.7,
        }
        
        weight = domain_weights.get(domain, 1.0)
        return gap_priority * weight
    
    def process_answer(
        self,
        question: str,
        answer: str,
        domain: str = ""
    ) -> Dict:
        """
        Process a user's answer to a proactive question.
        
        Args:
            question: The question that was asked
            answer: The user's answer
            domain: Optional domain for the question
            
        Returns:
            Dict with processing result
        """
        try:
            if domain:
                self._answered_domains.add(domain)
            
            # Add to training data
            self.memory.add_training_example(
                context=question,
                response=answer,
                source="active_learning",
                metadata={'domain': domain}
            )
            
            # Extract any facts from the answer
            extracted_facts = self._extract_facts_from_answer(question, answer)
            
            # Add extracted facts to personality
            for fact in extracted_facts:
                self.personality.add_fact(fact)
            
            return {
                'success': True,
                'extracted_facts': extracted_facts,
                'domain': domain
            }
            
        except Exception as e:
            logger.error(f"Error processing answer: {e}")
            return {'success': False, 'error': str(e)}
    
    def _extract_facts_from_answer(
        self,
        question: str,
        answer: str
    ) -> List[str]:
        """Use LLM to extract factual statements from an answer."""
        if len(answer) < 10:
            return []
        
        prompt = f"""Extract key facts from this Q&A as brief statements.

Question: {question}
Answer: {answer}

List each fact on a new line, starting with "- ". Be specific and concise.
Only list clear, factual information. If no clear facts, respond with "None".

Facts:"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=200,
                temperature=0.3
            )
            
            facts = []
            for line in response.split('\n'):
                line = line.strip()
                if line.startswith('- '):
                    fact = line[2:].strip()
                    if fact and fact.lower() != 'none':
                        facts.append(fact)
            
            return facts[:5]  # Limit to 5 facts
            
        except Exception as e:
            logger.error(f"Error extracting facts: {e}")
            return []
    
    def get_learning_stats(self) -> Dict:
        """Get statistics about active learning progress."""
        gaps = self.detect_knowledge_gaps()
        
        total_coverage = sum(gaps.values()) / len(gaps) if gaps else 0
        
        return {
            'overall_coverage': round(total_coverage * 100, 1),
            'domain_coverage': {k: round(v * 100, 1) for k, v in gaps.items()},
            'questions_asked': len(self._asked_questions),
            'domains_addressed': len(self._answered_domains),
            'available_domains': list(self.KNOWLEDGE_DOMAINS.keys())
        }
    
    def reset_asked_questions(self):
        """Reset the asked questions tracking."""
        self._asked_questions.clear()


# Singleton instance
_active_learning_service: Optional[ActiveLearningService] = None


def get_active_learning_service() -> ActiveLearningService:
    """Get the singleton active learning service instance."""
    global _active_learning_service
    if _active_learning_service is None:
        _active_learning_service = ActiveLearningService()
    return _active_learning_service

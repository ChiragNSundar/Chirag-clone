"""
Thinking Service - Recursive thinking / inner monologue for complex questions.
Implements chain-of-thought reasoning before generating responses.
"""
from typing import Dict, Optional, List, Tuple
import re

from .llm_service import get_llm_service
from .logger import get_logger

logger = get_logger(__name__)


class ThinkingService:
    """Service for generating inner monologue / thinking process before responses."""
    
    def __init__(self):
        self.llm = get_llm_service()
        
        # Keywords that suggest complex questions needing thinking
        self.COMPLEXITY_INDICATORS = [
            'why', 'how', 'explain', 'compare', 'analyze', 'what if',
            'should i', 'help me decide', 'pros and cons', 'difference between',
            'is it better', 'opinion on', 'think about', 'advice',
            'evaluate', 'recommend', 'strategy', 'plan', 'approach'
        ]
        
        # Minimum word count for considering thinking
        self.MIN_WORDS_FOR_THINKING = 5
        
        # Complexity threshold (0-1)
        self.COMPLEXITY_THRESHOLD = 0.4
    
    def should_think(self, message: str) -> bool:
        """
        Determine if a message is complex enough to warrant thinking.
        
        Args:
            message: The user's message
            
        Returns:
            True if thinking should be applied
        """
        if not message:
            return False
        
        message_lower = message.lower()
        words = message.split()
        
        # Too short - no thinking needed
        if len(words) < self.MIN_WORDS_FOR_THINKING:
            return False
        
        # Check for complexity indicators
        indicator_count = sum(
            1 for indicator in self.COMPLEXITY_INDICATORS 
            if indicator in message_lower
        )
        
        # Check for question marks
        question_count = message.count('?')
        
        # Calculate complexity score
        complexity = (indicator_count * 0.2) + (question_count * 0.15) + (len(words) / 50 * 0.15)
        
        return complexity >= self.COMPLEXITY_THRESHOLD
    
    def generate_thinking(
        self,
        message: str,
        personality_context: str = "",
        relevant_memories: List[str] = None
    ) -> Tuple[str, List[Dict]]:
        """
        Generate inner monologue / thinking process before answering.
        
        Args:
            message: The user's message
            personality_context: Context about the user's personality
            relevant_memories: Relevant core memories for context
            
        Returns:
            Tuple of (thinking_text, thinking_steps)
        """
        relevant_memories = relevant_memories or []
        
        memory_context = ""
        if relevant_memories:
            memory_context = "\n".join([f"- {m}" for m in relevant_memories[:5]])
        
        thinking_prompt = f"""You are the inner monologue of a digital clone. Before responding to this message, think through it step by step.

{personality_context}

{f"Relevant memories about this person:" + chr(10) + memory_context if memory_context else ""}

Message to think about: "{message}"

Think through this like you're talking to yourself:
1. What is the person really asking?
2. What relevant knowledge or memories do I have?
3. What are different perspectives or angles?
4. What would be the most authentic/helpful response?

Format your thinking as a brief internal monologue (2-4 sentences), then list key reasoning steps.

THINKING:"""

        try:
            response = self.llm.generate(
                prompt=thinking_prompt,
                max_tokens=300,
                temperature=0.7
            )
            
            # Parse thinking steps
            thinking_text, steps = self._parse_thinking(response)
            
            return thinking_text, steps
            
        except Exception as e:
            logger.error(f"Error generating thinking: {e}")
            return "", []
    
    def _parse_thinking(self, response: str) -> Tuple[str, List[Dict]]:
        """Parse the thinking response into text and structured steps."""
        lines = response.strip().split('\n')
        
        thinking_text = ""
        steps = []
        current_step = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for numbered steps
            step_match = re.match(r'^(\d+)\.\s*(.+)', line)
            if step_match:
                step_num = step_match.group(1)
                step_content = step_match.group(2)
                steps.append({
                    'step': int(step_num),
                    'content': step_content
                })
            elif not steps:
                # Before numbered steps - this is thinking text
                thinking_text += line + " "
        
        return thinking_text.strip(), steps
    
    def enhance_response_with_reasoning(
        self,
        response: str,
        thinking_steps: List[Dict]
    ) -> str:
        """
        Optionally enhance a response by incorporating reasoning.
        This can make responses feel more thoughtful.
        """
        if not thinking_steps:
            return response
        
        # For now, just return the response
        # Could be enhanced to subtly incorporate reasoning
        return response
    
    def get_thinking_summary(self, thinking_text: str, steps: List[Dict]) -> Dict:
        """Get a summary of the thinking process for UI display."""
        return {
            'thinking': thinking_text,
            'steps': steps,
            'step_count': len(steps),
            'has_thinking': bool(thinking_text or steps)
        }


# Singleton instance
_thinking_service: Optional[ThinkingService] = None


def get_thinking_service() -> ThinkingService:
    """Get the singleton thinking service instance."""
    global _thinking_service
    if _thinking_service is None:
        _thinking_service = ThinkingService()
    return _thinking_service

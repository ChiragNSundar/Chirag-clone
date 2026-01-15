"""
Chat Service - Orchestrates the chat generation process.
Now includes active learning, analytics tracking, confidence scoring,
knowledge base (RAG), vision support, and web search.
"""
from typing import List, Dict, Optional, Tuple
import time
from .llm_service import get_llm_service
from .personality_service import get_personality_service
from .memory_service import get_memory_service
from .learning_service import get_learning_service
from .analytics_service import get_analytics_service
from .mood_service import get_mood_service
from .knowledge_service import get_knowledge_service
from .search_service import get_search_service
from .vision_service import get_vision_service
from config import Config


class ChatService:
    """Main chat service that generates responses like the user."""
    
    # Simple LRU cache for responses
    _response_cache = {}
    _cache_max_size = 100
    
    def __init__(self):
        self.llm = get_llm_service()
        self.personality = get_personality_service()
        self.memory = get_memory_service()
        self.learning = get_learning_service()
    
    def _get_cache_key(self, message: str) -> str:
        """Generate a cache key for a message."""
        return message.strip().lower()[:100]
    
    def _check_cache(self, message: str) -> str:
        """Check if response is cached."""
        key = self._get_cache_key(message)
        return self._response_cache.get(key)
    
    def _add_to_cache(self, message: str, response: str):
        """Add response to cache."""
        if len(self._response_cache) >= self._cache_max_size:
            # Remove oldest (first) item
            oldest_key = next(iter(self._response_cache))
            del self._response_cache[oldest_key]
        
        key = self._get_cache_key(message)
        self._response_cache[key] = response
    
    # Global setting for continuous learning
    continuous_learning = False
    
    def generate_response(
        self,
        user_message: str,
        session_id: str = "default",
        include_examples: bool = True,
        training_mode: bool = False,
        enable_thinking: bool = True
    ) -> Tuple[str, float, dict, dict]:
        """
        Generate a response as the user's clone.
        
        Args:
            user_message: The incoming message to respond to
            session_id: Conversation session ID for context
            include_examples: Whether to include few-shot examples
            training_mode: If true, asks probing questions to learn
            enable_thinking: Whether to use thinking service for complex queries
            
        Returns:
            Tuple of (response, confidence, mood, thinking_data)
        """
        # Get conversation history
        history = self.memory.get_conversation_history(
            session_id, 
            limit=Config.MAX_CONTEXT_MESSAGES
        )
        
        # Build the system prompt with personality
        system_prompt = self.personality.get_system_prompt()
        
        # MOOD SYSTEM INJECTION
        try:
            mood_service = get_mood_service()
            current_mood = mood_service.update_mood_from_interaction(user_message)
            
            # Inject mood instruction if not in training mode (training should be neutral/curious)
            if not training_mode:
                system_prompt += f"\n\nCURRENT MOOD: {current_mood['mood'].upper()}\nINSTRUCTION: {current_mood['prompt']}"
        except Exception as e:
            print(f"Mood error: {e}")

        # For training mode, add instructions to have deeper conversations
        if training_mode:
            system_prompt = self._get_training_prompt()
        
        # Find similar examples for few-shot learning
        examples = []
        search_results = []
        if include_examples and not training_mode:
            examples = self.memory.find_similar_examples(
                user_message,
                n_results=Config.MAX_FEW_SHOT_EXAMPLES
            )
            
            if examples:
                examples_text = self._format_examples(examples)
                system_prompt += f"\n\nHere are examples of how you respond:\n{examples_text}"
        
        # KNOWLEDGE BASE (RAG) INJECTION
        if not training_mode:
            try:
                knowledge = get_knowledge_service()
                knowledge_chunks = knowledge.query_knowledge(user_message, n_results=3)
                if knowledge_chunks:
                    knowledge_text = knowledge.format_for_llm(knowledge_chunks)
                    system_prompt += f"\n\n{knowledge_text}"
            except Exception as e:
                print(f"Knowledge query error: {e}")
        
        # WEB SEARCH INJECTION
        if not training_mode:
            try:
                search = get_search_service()
                if search.is_available() and search.should_search(user_message):
                    search_results = search.search(user_message, max_results=3)
                    if search_results:
                        search_text = search.format_for_llm(search_results, user_message)
                        system_prompt += f"\n\n{search_text}"
            except Exception as e:
                print(f"Web search error: {e}")
        
        # Build message history for LLM
        messages = self._build_messages(history, user_message)
        
        # THINKING PROCESS - Chain-of-thought for complex queries
        thinking_data = {'thinking': '', 'steps': [], 'has_thinking': False}
        if enable_thinking and not training_mode:
            try:
                from .thinking_service import get_thinking_service
                thinking_service = get_thinking_service()
                
                if thinking_service.should_think(user_message):
                    personality_context = f"You are {self.personality.get_profile().name}'s clone."
                    thinking_text, thinking_steps = thinking_service.generate_thinking(
                        message=user_message,
                        personality_context=personality_context
                    )
                    thinking_data = {
                        'thinking': thinking_text,
                        'steps': thinking_steps,
                        'has_thinking': bool(thinking_text or thinking_steps)
                    }
                    
                    # Inject thinking into prompt for better response
                    if thinking_text:
                        system_prompt += f"\n\nBefore responding, you thought: {thinking_text}"
            except Exception as e:
                print(f"Thinking service error: {e}")
        
        # Generate response
        response = self.llm.generate_response(
            system_prompt=system_prompt,
            messages=messages
        )
        
        # Clean up the response
        response = self._clean_response(response)
        
        # Active learning: only in training mode
        if training_mode:
            try:
                self.learning.learn_from_exchange(
                    user_message=user_message,
                    bot_response=response,
                    personality_service=self.personality,
                    memory_service=self.memory
                )
            except Exception as e:
                print(f"Learning error (non-critical): {e}")
        
        # Continuous learning mode - learn from all chats if enabled
        if ChatService.continuous_learning and not training_mode:
            try:
                self.learning.learn_from_exchange(
                    user_message=user_message,
                    bot_response=response,
                    personality_service=self.personality,
                    memory_service=self.memory
                )
            except Exception as e:
                print(f"Continuous learning error: {e}")
        
        # Discovery questions only in training mode
        if training_mode and self.learning.should_ask_question():
            question = self.learning.get_discovery_question()
            if question:
                response = f"{response}\n\n{question}"
        
        # Calculate confidence score based on examples found
        confidence = self._calculate_confidence(examples, response)
        
        # Track analytics
        response_time = int((time.time() - start_time) * 1000) if 'start_time' in dir() else 0
        try:
            analytics = get_analytics_service()
            analytics.log_conversation(
                user_message=user_message,
                bot_response=response,
                response_time_ms=response_time,
                confidence=confidence,
                is_training=training_mode
            )
        except:
            pass
        
        # Store the response
        self.memory.add_conversation_message(session_id, "assistant", response)
        
        return response, confidence, current_mood if 'current_mood' in locals() else None, thinking_data
    
    def _calculate_confidence(self, examples: List[Dict], response: str) -> float:
        """Calculate confidence score based on available context."""
        confidence = 0.5  # Base confidence
        
        # More examples = higher confidence
        if len(examples) >= 3:
            confidence += 0.2
        elif len(examples) >= 1:
            confidence += 0.1
        
        # Longer, more detailed responses = higher confidence
        if len(response) > 100:
            confidence += 0.1
        
        # Check if response uses learned quirks
        profile = self.personality.get_profile()
        for quirk in profile.typing_quirks[:5]:
            if quirk.lower() in response.lower():
                confidence += 0.05
                break
        
        return min(confidence, 1.0)
    
    def _get_training_prompt(self) -> str:
        """Get system prompt for training mode - encourages deep conversation."""
        profile = self.personality.get_profile()
        
        return f"""You are an AI interviewer helping to learn about {profile.name}'s personality, views, and communication style.

YOUR GOAL: Have engaging, deep conversations to understand how {profile.name} thinks and communicates.

CONVERSATION STYLE:
- Ask thoughtful follow-up questions
- Be curious and genuinely interested
- Dig deeper into their opinions and experiences
- Ask "why" and "how" questions
- Share observations about their responses
- Be conversational, not interrogative

TOPICS TO EXPLORE:
- Their opinions on things
- How they handle situations
- Their interests and passions
- Their communication preferences
- Their values and beliefs
- What makes them laugh or frustrated

IMPORTANT:
- Keep responses relatively short (2-3 sentences max)
- One question at a time
- React to what they say before asking another question
- Be warm and friendly, not robotic
- Occasionally share a relevant thought before asking

Remember: Every response teaches you something about {profile.name}. Pay attention to:
- How formal or casual they are
- Their word choices
- Their emoji usage
- The length of their messages
- Their sense of humor"""
    
    def _format_examples(self, examples: List[Dict]) -> str:
        """Format examples for inclusion in the prompt."""
        formatted = []
        for i, ex in enumerate(examples, 1):
            formatted.append(f"Example {i}:")
            formatted.append(f"  Them: {ex['context']}")
            formatted.append(f"  You: {ex['response']}")
            formatted.append("")
        return "\n".join(formatted)
    
    def _build_messages(
        self,
        history: List[Dict],
        current_message: str
    ) -> List[Dict[str, str]]:
        """Build the message list for the LLM."""
        messages = []
        
        # Add history
        for msg in history[-Config.MAX_CONTEXT_MESSAGES:]:
            messages.append({
                "role": msg['role'],
                "content": msg['content']
            })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": current_message
        })
        
        return messages
    
    def _clean_response(self, response: str) -> str:
        """Clean up the generated response."""
        # Remove any role prefixes the model might add
        prefixes_to_remove = [
            f"{self.personality.get_profile().name}:",
            "Assistant:",
            "You:",
            "Me:",
        ]
        
        response = response.strip()
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        return response
    
    def train_from_interaction(
        self,
        context: str,
        correction: str
    ) -> None:
        """
        Learn from a correction during interactive training.
        
        Args:
            context: The original context/question
            correction: The correct response you would give
        """
        # Add to memory
        self.memory.add_training_example(
            context=context,
            response=correction,
            source="training_corner"
        )
        
        # Also add to personality examples
        self.personality.add_example(context, correction)
        
        # Analyze the correction for style patterns
        try:
            analysis = self.learning.analyze_message(correction)
            self.learning.learn_from_exchange(
                user_message=context,
                bot_response=correction,
                personality_service=self.personality,
                memory_service=self.memory
            )
        except Exception as e:
            print(f"Learning from correction error: {e}")
    
    def get_training_stats(self) -> Dict:
        """Get statistics about training data."""
        return self.memory.get_training_stats()


# Singleton instance
_chat_service = None

def get_chat_service() -> ChatService:
    """Get the singleton chat service instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

"""
LLM Service - Handles interactions with various LLM providers.
Enhanced with retry logic, circuit breaker, and timeouts.
Supports Gemini (primary), OpenAI (fallback), Anthropic, and Ollama.
"""
import json
import time
import requests
from typing import List, Dict, Optional
from threading import Lock
from config import Config
from services.logger import get_logger

logger = get_logger(__name__)


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for fault tolerance.
    States: CLOSED (normal), OPEN (blocking), HALF_OPEN (testing)
    """
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self._lock = Lock()
    
    def can_proceed(self) -> bool:
        """Check if request can proceed."""
        with self._lock:
            if self.state == 'CLOSED':
                return True
            
            if self.state == 'OPEN':
                # Check if reset timeout has passed
                if time.time() - self.last_failure_time >= self.reset_timeout:
                    self.state = 'HALF_OPEN'
                    logger.info("Circuit breaker entering HALF_OPEN state")
                    return True
                return False
            
            # HALF_OPEN - allow one request to test
            return True
    
    def record_success(self):
        """Record a successful request."""
        with self._lock:
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                logger.info("Circuit breaker reset to CLOSED state")
            self.failures = 0
    
    def record_failure(self):
        """Record a failed request."""
        with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()
            
            if self.failures >= self.failure_threshold:
                self.state = 'OPEN'
                logger.warning(f"Circuit breaker OPEN after {self.failures} failures")
    
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == 'OPEN'


class LLMService:
    """Unified interface for different LLM providers with automatic fallback, retry, and circuit breaker."""
    
    def __init__(self):
        self.provider = Config.LLM_PROVIDER
        self.fallback_provider = 'openai' if self.provider == 'gemini' else None
        self.client = None
        self.fallback_client = None
        self.model = None
        self._init_error = None
        self._lazy_init_done = False
        
        # Resilience settings
        self.max_retries = getattr(Config, 'LLM_RETRY_COUNT', 3)
        self.request_timeout = getattr(Config, 'LLM_REQUEST_TIMEOUT', 30)
        
        # Circuit breaker
        failure_threshold = getattr(Config, 'CIRCUIT_BREAKER_THRESHOLD', 5)
        reset_timeout = getattr(Config, 'CIRCUIT_BREAKER_TIMEOUT', 60)
        self._circuit_breaker = CircuitBreaker(failure_threshold, reset_timeout)
    
    def _lazy_init(self):
        """Lazy initialization of LLM client - only when first needed."""
        if self._lazy_init_done:
            return
        self._lazy_init_done = True
        
        try:
            self._init_client()
        except Exception as e:
            self._init_error = str(e)
            logger.error(f"LLM initialization error: {e}")
    
    def _init_client(self):
        """Initialize the appropriate LLM client based on provider."""
        if self.provider == 'gemini':
            if not Config.GEMINI_API_KEY or Config.GEMINI_API_KEY == 'your-gemini-api-key-here':
                raise ValueError("Gemini API key not configured. Please set GEMINI_API_KEY in .env file.")
            
            import google.generativeai as genai
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.client = genai
            self.model = Config.GEMINI_MODEL
            
            # Also init fallback if available
            if Config.OPENAI_API_KEY and Config.OPENAI_API_KEY != 'sk-your-openai-key-here':
                try:
                    from openai import OpenAI
                    self.fallback_client = OpenAI(api_key=Config.OPENAI_API_KEY)
                except Exception as e:
                    logger.warning(f"OpenAI fallback init failed: {e}")
                    self.fallback_client = None
            else:
                self.fallback_client = None
                
        elif self.provider == 'openai':
            if not Config.OPENAI_API_KEY or Config.OPENAI_API_KEY == 'sk-your-openai-key-here':
                raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY in .env file.")
            
            from openai import OpenAI
            self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
            self.model = Config.OPENAI_MODEL
            self.fallback_client = None
            
        elif self.provider == 'ollama':
            self.client = None  # Use requests for Ollama
            self.model = Config.OLLAMA_MODEL
            self.fallback_client = None
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Execute function with exponential backoff retry.
        Returns (success, result_or_error)
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                result = func(*args, **kwargs)
                return True, result
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                
                # Don't retry on certain errors
                if 'api key' in error_msg or 'authentication' in error_msg:
                    logger.error(f"Authentication error, not retrying: {e}")
                    return False, e
                
                if 'quota' in error_msg or 'limit' in error_msg:
                    logger.error(f"Quota/rate limit error, not retrying: {e}")
                    return False, e
                
                # Exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s...
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
        
        return False, last_error
    
    def generate_response(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """
        Generate a response from the LLM with automatic fallback, retry, and circuit breaker.
        
        Args:
            system_prompt: The system message defining bot personality
            messages: List of message dicts with 'role' and 'content'
            temperature: Creativity of responses (0-1)
            max_tokens: Maximum response length
            
        Returns:
            Generated response text
        """
        # Lazy initialization
        self._lazy_init()
        
        if self._init_error:
            return f"I'm having trouble connecting to the AI service. Please check your API key configuration."
        
        # Check circuit breaker
        if not self._circuit_breaker.can_proceed():
            logger.warning("Circuit breaker is OPEN, blocking request")
            if self.fallback_client:
                logger.info("Attempting fallback while circuit is open")
                return self._try_fallback(system_prompt, messages, temperature, max_tokens)
            return "I'm temporarily unavailable. Please try again in a minute."
        
        temperature = temperature or Config.TEMPERATURE
        max_tokens = max_tokens or Config.MAX_TOKENS
        
        # Try primary provider with retry
        success, result = self._try_primary(system_prompt, messages, temperature, max_tokens)
        
        if success:
            self._circuit_breaker.record_success()
            return result
        
        # Primary failed - record failure
        self._circuit_breaker.record_failure()
        
        # Try fallback
        if self.fallback_client and self.fallback_provider == 'openai':
            logger.info("Falling back to OpenAI...")
            return self._try_fallback(system_prompt, messages, temperature, max_tokens)
        
        # No fallback available
        return self._format_error_message(result)
    
    def _try_primary(self, system_prompt, messages, temperature, max_tokens):
        """Try primary provider with retry logic."""
        def generate():
            if self.provider == 'gemini':
                return self._gemini_generate(system_prompt, messages, temperature, max_tokens)
            elif self.provider == 'openai':
                return self._openai_generate(system_prompt, messages, temperature, max_tokens)
            elif self.provider == 'ollama':
                return self._ollama_generate(system_prompt, messages, temperature, max_tokens)
        
        return self._retry_with_backoff(generate)
    
    def _try_fallback(self, system_prompt, messages, temperature, max_tokens):
        """Try fallback provider."""
        try:
            return self._openai_fallback_generate(system_prompt, messages, temperature, max_tokens)
        except Exception as e:
            logger.error(f"Fallback also failed: {e}")
            return self._format_error_message(e)
    
    def _format_error_message(self, error) -> str:
        """Format error into a user-friendly message."""
        error_msg = str(error).lower() if error else 'unknown error'
        
        if 'api key' in error_msg or 'authentication' in error_msg:
            return "API key seems invalid. Please check your API configuration."
        elif 'quota' in error_msg or 'limit' in error_msg or 'rate' in error_msg:
            return "API limit reached. Please try again later."
        elif 'timeout' in error_msg:
            return "Request timed out. Please try again."
        elif 'connection' in error_msg:
            return "Could not connect to AI service. Please check your internet connection."
        else:
            return "I couldn't generate a response. Please try again."
    
    def _gemini_generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using Google Gemini API."""
        model = self.client.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
        )
        
        # Convert messages to Gemini format
        chat_history = []
        for msg in messages[:-1]:  # All but last message
            role = "user" if msg['role'] == 'user' else "model"
            chat_history.append({
                "role": role,
                "parts": [msg['content']]
            })
        
        chat = model.start_chat(history=chat_history)
        
        # Send the last message
        last_msg = messages[-1]['content'] if messages else ""
        response = chat.send_message(last_msg)
        
        return response.text
    
    def _openai_generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using OpenAI API."""
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=self.request_timeout
        )
        
        return response.choices[0].message.content
    
    def _openai_fallback_generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using OpenAI API as fallback."""
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        response = self.fallback_client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=self.request_timeout
        )
        
        return response.choices[0].message.content
    

    
    def _ollama_generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using local Ollama."""
        # Format messages for Ollama
        prompt = f"System: {system_prompt}\n\n"
        for msg in messages:
            role = "Human" if msg['role'] == 'user' else "Assistant"
            prompt += f"{role}: {msg['content']}\n"
        prompt += "Assistant:"
        
        try:
            response = requests.post(
                f"{Config.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                return response.json().get('response', '')
            else:
                raise Exception(f"Ollama error: {response.text}")
        except requests.exceptions.ConnectionError:
            return "Ollama is not running. Please start Ollama with 'ollama serve' or switch to a cloud provider."
        except requests.exceptions.Timeout:
            return "Ollama request timed out. The model might be loading."
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get text embedding for similarity search.
        Uses Gemini embeddings if available, otherwise sentence-transformers.
        """
        self._lazy_init()
        
        if self.provider == 'gemini' and self.client and Config.GEMINI_API_KEY:
            try:
                result = self.client.embed_content(
                    model="models/embedding-001",
                    content=text,
                    task_type="retrieval_document"
                )
                return result['embedding']
            except Exception as e:
                logger.warning(f"Gemini embedding failed, using local: {e}")
                
        if self.provider == 'openai' and self.client and Config.OPENAI_API_KEY:
            try:
                response = self.client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                return response.data[0].embedding
            except Exception as e:
                logger.warning(f"OpenAI embedding failed, using local: {e}")
        
        # Fallback to local sentence-transformers
        from sentence_transformers import SentenceTransformer
        if not hasattr(self, '_embedding_model'):
            self._embedding_model = SentenceTransformer(Config.EMBEDDING_MODEL)
        return self._embedding_model.encode(text).tolist()
    
    def get_circuit_state(self) -> dict:
        """Get current circuit breaker state for health checks."""
        return {
            'state': self._circuit_breaker.state,
            'failures': self._circuit_breaker.failures,
            'is_open': self._circuit_breaker.is_open()
        }


# Singleton instance
_llm_service = None

def get_llm_service() -> LLMService:
    """Get the singleton LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

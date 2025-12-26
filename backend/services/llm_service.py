"""
LLM Service - Handles interactions with various LLM providers.
Supports Gemini (primary), OpenAI (fallback), Anthropic, and Ollama.
"""
import json
import requests
from typing import List, Dict, Optional
from config import Config


class LLMService:
    """Unified interface for different LLM providers with automatic fallback."""
    
    def __init__(self):
        self.provider = Config.LLM_PROVIDER
        self.fallback_provider = 'openai' if self.provider == 'gemini' else None
        self.client = None
        self.fallback_client = None
        self.model = None
        self._init_error = None
        self._lazy_init_done = False
    
    def _lazy_init(self):
        """Lazy initialization of LLM client - only when first needed."""
        if self._lazy_init_done:
            return
        self._lazy_init_done = True
        
        try:
            self._init_client()
        except Exception as e:
            self._init_error = str(e)
            print(f"LLM initialization error: {e}")
    
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
                    print(f"OpenAI fallback init failed: {e}")
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
            
        elif self.provider == 'anthropic':
            if not Config.ANTHROPIC_API_KEY or Config.ANTHROPIC_API_KEY == 'sk-ant-your-anthropic-key-here':
                raise ValueError("Anthropic API key not configured. Please set ANTHROPIC_API_KEY in .env file.")
            
            import anthropic
            self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            self.model = Config.ANTHROPIC_MODEL
            self.fallback_client = None
            
        elif self.provider == 'ollama':
            self.client = None  # Use requests for Ollama
            self.model = Config.OLLAMA_MODEL
            self.fallback_client = None
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")
    
    def generate_response(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None
    ) -> str:
        """
        Generate a response from the LLM with automatic fallback.
        
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
            return f"I'm having trouble connecting to the AI service. Error: {self._init_error}. Please check your API key configuration."
        
        temperature = temperature or Config.TEMPERATURE
        max_tokens = max_tokens or Config.MAX_TOKENS
        
        try:
            if self.provider == 'gemini':
                return self._gemini_generate(system_prompt, messages, temperature, max_tokens)
            elif self.provider == 'openai':
                return self._openai_generate(system_prompt, messages, temperature, max_tokens)
            elif self.provider == 'anthropic':
                return self._anthropic_generate(system_prompt, messages, temperature, max_tokens)
            elif self.provider == 'ollama':
                return self._ollama_generate(system_prompt, messages, temperature, max_tokens)
        except Exception as e:
            error_msg = str(e)
            print(f"Primary provider ({self.provider}) failed: {error_msg}")
            
            # Try fallback
            if self.fallback_client and self.fallback_provider == 'openai':
                print("Falling back to OpenAI...")
                try:
                    return self._openai_fallback_generate(system_prompt, messages, temperature, max_tokens)
                except Exception as fallback_error:
                    print(f"Fallback also failed: {fallback_error}")
                    return f"I'm having trouble responding right now. Error: {error_msg}"
            else:
                # Return a friendly error message instead of crashing
                if "API key" in error_msg.lower() or "authentication" in error_msg.lower():
                    return "API key seems invalid. Please check your GEMINI_API_KEY in the .env file."
                elif "quota" in error_msg.lower() or "limit" in error_msg.lower():
                    return "API quota exceeded. Please try again later or check your API plan."
                else:
                    return f"I couldn't generate a response. Error: {error_msg}"
    
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
            max_tokens=max_tokens
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
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content
    
    def _anthropic_generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using Anthropic API."""
        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response.content[0].text
    
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
                timeout=30
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
                print(f"Gemini embedding failed, using local: {e}")
                
        if self.provider == 'openai' and self.client and Config.OPENAI_API_KEY:
            try:
                response = self.client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                return response.data[0].embedding
            except Exception as e:
                print(f"OpenAI embedding failed, using local: {e}")
        
        # Fallback to local sentence-transformers
        from sentence_transformers import SentenceTransformer
        if not hasattr(self, '_embedding_model'):
            self._embedding_model = SentenceTransformer(Config.EMBEDDING_MODEL)
        return self._embedding_model.encode(text).tolist()


# Singleton instance
_llm_service = None

def get_llm_service() -> LLMService:
    """Get the singleton LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

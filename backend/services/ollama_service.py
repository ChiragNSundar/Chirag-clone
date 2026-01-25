"""
Ollama Service - Handles interactions with local Ollama instance.
Provides methods for chat generation, embedding, and model management.
"""
import requests
import json
from typing import List, Dict, Optional, Any, Generator
from config import Config
from services.logger import get_logger

logger = get_logger(__name__)

class OllamaService:
    """Service to interface with Ollama API."""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or Config.OLLAMA_BASE_URL
        self.default_model = Config.OLLAMA_MODEL
        
    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
            
    def list_models(self) -> List[Dict[str, Any]]:
        """List available local models."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('models', [])
            return []
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    def generate_chat(
        self, 
        messages: List[Dict[str, str]], 
        model: str = None, 
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False
    ) -> str | Generator:
        """
        Generate chat response from Ollama.
        """
        model = model or self.default_model
        
        # Format for Ollama API
        # Ollama supports 'messages' key directly in /api/chat similar to OpenAI
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            if stream:
                return self._stream_response(payload)
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=Config.LLM_REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                return response.json().get('message', {}).get('content', '')
            else:
                logger.error(f"Ollama API error: {response.text}")
                raise Exception(f"Ollama API returned {response.status_code}")
                
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    def _stream_response(self, payload: Dict) -> Generator:
        """Yield chunks from streaming response."""
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=Config.LLM_REQUEST_TIMEOUT
        )
        
        for line in response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    if 'message' in chunk:
                        yield chunk['message']['content']
                except json.JSONDecodeError:
                    pass

    def get_embeddings(self, text: str, model: str = "nomic-embed-text") -> List[float]:
        """Get vector embeddings from Ollama."""
        try:
            payload = {
                "model": model,
                "prompt": text
            }
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('embedding', [])
            return []
        except Exception as e:
            logger.error(f"Ollama embedding failed: {e}")
            return []

# Singleton
_ollama_service = None

def get_ollama_service() -> OllamaService:
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService()
    return _ollama_service

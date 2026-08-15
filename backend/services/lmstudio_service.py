"""
LM Studio Service - Handles interactions with local LM Studio instance.
Uses the OpenAI-compatible API endpoint (http://localhost:1234/v1).

LM Studio is the PRIMARY and ONLY LLM provider for this project.
No cloud APIs are used — all inference stays local.
"""
from __future__ import annotations
import json
import requests
from typing import List, Dict, Optional, Any, Generator, Union
from config import Config
from services.logger import get_logger

logger = get_logger(__name__)


class LMStudioService:
    """Service to interface with LM Studio's OpenAI-compatible API."""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or getattr(Config, 'LMSTUDIO_BASE_URL', 'http://localhost:1234')
        self.api_base = f"{self.base_url}/v1"
        self.default_model = getattr(Config, 'LMSTUDIO_MODEL', 'auto')

    def is_available(self) -> bool:
        """Check if LM Studio server is running and has a model loaded."""
        try:
            response = requests.get(f"{self.api_base}/models", timeout=3)
            if response.status_code == 200:
                data = response.json()
                models = data.get('data', [])
                if models:
                    logger.info(f"🖥️ LM Studio available with {len(models)} model(s) loaded")
                    return True
                else:
                    logger.warning("LM Studio running but no models loaded")
                    return False
            return False
        except requests.exceptions.ConnectionError:
            return False
        except Exception as e:
            logger.debug(f"LM Studio check failed: {e}")
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        """List available models loaded in LM Studio."""
        try:
            response = requests.get(f"{self.api_base}/models", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            return []
        except Exception as e:
            logger.error(f"Failed to list LM Studio models: {e}")
            return []

    def get_loaded_model(self) -> Optional[str]:
        """Get the currently loaded model ID from LM Studio."""
        models = self.list_models()
        if models:
            # Return the first loaded model (LM Studio usually loads one at a time)
            return models[0].get('id', None)
        return None

    def _resolve_model(self, model: str = None) -> str:
        """Resolve which model to use. Auto-detects if set to 'auto'."""
        model = model or self.default_model
        if model == 'auto':
            detected = self.get_loaded_model()
            if detected:
                return detected
            raise RuntimeError(
                "LM Studio model set to 'auto' but no model is loaded. "
                "Please load a model in LM Studio or set LMSTUDIO_MODEL in .env"
            )
        return model

    def generate_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False
    ) -> Union[str, Generator]:
        """
        Generate chat response from LM Studio via OpenAI-compatible API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model ID (auto-detected if None or 'auto')
            temperature: Creativity parameter (0-2)
            max_tokens: Maximum response tokens
            stream: Whether to stream the response

        Returns:
            Generated response text, or a generator if streaming
        """
        resolved_model = self._resolve_model(model)

        payload = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        try:
            if stream:
                return self._stream_response(payload)

            response = requests.post(
                f"{self.api_base}/chat/completions",
                json=payload,
                timeout=getattr(Config, 'LLM_REQUEST_TIMEOUT', 120)
            )

            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                error_detail = response.text[:500]
                logger.error(f"LM Studio API error {response.status_code}: {error_detail}")
                raise Exception(f"LM Studio API returned {response.status_code}: {error_detail}")

        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                "Cannot connect to LM Studio. Please ensure LM Studio is running "
                f"at {self.base_url} with a model loaded."
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(
                "LM Studio request timed out. The model may be processing a complex request."
            )
        except Exception as e:
            logger.error(f"LM Studio generation failed: {e}")
            raise

    def _stream_response(self, payload: Dict) -> Generator:
        """Yield chunks from streaming SSE response."""
        response = requests.post(
            f"{self.api_base}/chat/completions",
            json=payload,
            stream=True,
            timeout=getattr(Config, 'LLM_REQUEST_TIMEOUT', 120)
        )

        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    if data_str.strip() == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        pass

    def get_embeddings(self, text: str, model: str = None) -> List[float]:
        """
        Get vector embeddings from LM Studio.

        Note: LM Studio supports embeddings if an embedding model is loaded.
        Falls back to empty list if not available.
        """
        try:
            payload = {
                "model": model or self.default_model,
                "input": text
            }
            response = requests.post(
                f"{self.api_base}/embeddings",
                json=payload,
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('data', [{}])[0].get('embedding', [])
            return []
        except Exception as e:
            logger.debug(f"LM Studio embedding not available: {e}")
            return []


# Singleton
_lmstudio_service = None


def get_lmstudio_service() -> LMStudioService:
    """Get the singleton LM Studio service instance."""
    global _lmstudio_service
    if _lmstudio_service is None:
        _lmstudio_service = LMStudioService()
    return _lmstudio_service

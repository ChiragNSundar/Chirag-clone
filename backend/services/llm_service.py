"""
LLM Service - Handles interactions with LM Studio (local LLM).
No cloud APIs are used. If LM Studio is not running, the system
falls back to RAG + context files for responses.

Includes retry logic, circuit breaker, and timeouts.
"""
import json
import time
import requests
from typing import List, Dict, Optional, Any
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
    """
    Unified LLM interface using LM Studio as the sole provider.
    
    If LM Studio is unavailable, returns a flag indicating
    the system should fall back to RAG + context files.
    """
    
    def __init__(self):
        self.provider = 'lmstudio'
        self.client = None
        self.model = None
        self._init_error = None
        self._lazy_init_done = False
        self._lmstudio_available = False
        
        # Resilience settings
        self.max_retries = getattr(Config, 'LLM_RETRY_COUNT', 2)
        self.request_timeout = getattr(Config, 'LLM_REQUEST_TIMEOUT', 120)
        
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
            logger.warning(f"LLM initialization: {e}. Will use RAG + context files as fallback.")
    
    def _init_client(self):
        """Initialize the LM Studio client."""
        from services.lmstudio_service import get_lmstudio_service
        
        lmstudio = get_lmstudio_service()
        self._lmstudio_available = lmstudio.is_available()
        
        if self._lmstudio_available:
            self.client = lmstudio
            self.model = Config.LMSTUDIO_MODEL
            logger.info(f"🖥️ LM Studio connected at {Config.LMSTUDIO_BASE_URL}")
        else:
            logger.warning(
                "🔌 LM Studio not available. Running in RAG-only mode. "
                "Start LM Studio with a model loaded for full AI responses."
            )

    def is_llm_available(self) -> bool:
        """Check if an LLM is currently available for generation."""
        self._lazy_init()
        if self._lmstudio_available:
            return True
        # Re-check in case LM Studio was started after init
        from services.lmstudio_service import get_lmstudio_service
        self._lmstudio_available = get_lmstudio_service().is_available()
        if self._lmstudio_available:
            self.client = get_lmstudio_service()
            self.model = Config.LMSTUDIO_MODEL
        return self._lmstudio_available
    
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
                
                # Don't retry on connection errors (LM Studio is down)
                if 'connection' in error_msg or 'connect' in error_msg:
                    logger.warning("LM Studio connection failed, not retrying")
                    return False, e
                
                # Exponential backoff for other errors
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
        Generate a response from LM Studio.
        
        If LM Studio is unavailable, returns a message indicating
        RAG-only mode. The chat service will handle context injection.
        
        Args:
            system_prompt: The system message defining bot personality
            messages: List of message dicts with 'role' and 'content'
            temperature: Creativity of responses (0-2)
            max_tokens: Maximum response length
            
        Returns:
            Generated response text
        """
        # Lazy initialization
        self._lazy_init()
        
        # Check if LLM is available
        if not self.is_llm_available():
            return self._rag_only_response()
        
        # Check circuit breaker
        if not self._circuit_breaker.can_proceed():
            logger.warning("Circuit breaker is OPEN, blocking LLM request")
            return self._rag_only_response()
        
        temperature = temperature or Config.TEMPERATURE
        max_tokens = max_tokens or Config.MAX_TOKENS
        
        # Try LM Studio with retry
        success, result = self._try_lmstudio(system_prompt, messages, temperature, max_tokens)
        
        if success:
            self._circuit_breaker.record_success()
            return result
        
        # LM Studio failed — record failure
        self._circuit_breaker.record_failure()
        self._lmstudio_available = False
        
        return self._rag_only_response()
    
    def _try_lmstudio(self, system_prompt, messages, temperature, max_tokens):
        """Try LM Studio with retry logic."""
        def generate():
            return self._lmstudio_generate(system_prompt, messages, temperature, max_tokens)
        
        return self._retry_with_backoff(generate)
    
    def _lmstudio_generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using LM Studio via LMStudioService."""
        from services.lmstudio_service import get_lmstudio_service
        
        # Prepare messages including system prompt
        lm_messages = [{"role": "system", "content": system_prompt}] + messages
        
        return get_lmstudio_service().generate_chat(
            messages=lm_messages,
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    def _rag_only_response(self) -> str:
        """
        Return a response indicating RAG-only mode.
        The chat service should detect this and use context files instead.
        """
        return (
            "I'm currently running in knowledge-base mode (LM Studio is not connected). "
            "I can still answer based on my stored knowledge and context files. "
            "For full conversational AI, please start LM Studio with a model loaded."
        )
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get text embedding for similarity search.
        Uses local sentence-transformers (always available, no LLM needed).
        """
        from sentence_transformers import SentenceTransformer
        if not hasattr(self, '_embedding_model'):
            self._embedding_model = SentenceTransformer(Config.EMBEDDING_MODEL)
        return self._embedding_model.encode(text).tolist()
    
    # ============= Custom Adapter Loading =============
    
    def load_custom_adapter(self, adapter_path: str) -> Dict[str, Any]:
        """
        Load a custom LoRA adapter for inference.
        
        For LM Studio, GGUF models can be loaded directly.
        The adapter would need to be merged with the base model first
        and exported as GGUF, then loaded in LM Studio.
        
        Args:
            adapter_path: Path to the trained adapter directory
            
        Returns:
            Dict with success status and adapter info
        """
        import os
        
        if not os.path.exists(adapter_path):
            return {"success": False, "error": f"Adapter not found: {adapter_path}"}
        
        # Check for adapter files
        adapter_config = os.path.join(adapter_path, "adapter_config.json")
        if not os.path.exists(adapter_config):
            return {"success": False, "error": "Invalid adapter: missing adapter_config.json"}
        
        # Store current adapter info
        self._current_adapter = adapter_path
        self._adapter_loaded = True
        
        # Check for GGUF export
        gguf_dir = os.path.join(adapter_path, "gguf")
        if os.path.exists(gguf_dir):
            gguf_files = [f for f in os.listdir(gguf_dir) if f.endswith('.gguf')]
            if gguf_files:
                logger.info(
                    f"Found GGUF export: {gguf_files[0]}. "
                    "Load this file in LM Studio to use the fine-tuned model."
                )
                return {
                    "success": True,
                    "adapter": os.path.basename(adapter_path),
                    "gguf_file": os.path.join(gguf_dir, gguf_files[0]),
                    "provider": "lmstudio",
                    "note": "Load the GGUF file in LM Studio to use this adapter."
                }
        
        logger.info(f"Adapter registered: {adapter_path}")
        return {
            "success": True,
            "adapter": os.path.basename(adapter_path),
            "path": adapter_path,
            "provider": self.provider,
            "note": "Merge adapter with base model and export as GGUF for LM Studio."
        }
    
    def unload_adapter(self) -> Dict[str, Any]:
        """
        Unload the current custom adapter and revert to base model.
        
        Returns:
            Dict with success status
        """
        if not hasattr(self, '_adapter_loaded') or not self._adapter_loaded:
            return {"success": True, "message": "No adapter was loaded"}
        
        # Reset to default model
        self.model = Config.LMSTUDIO_MODEL
        
        self._current_adapter = None
        self._adapter_loaded = False
        
        logger.info(f"Adapter unloaded, reverted to base model: {self.model}")
        return {
            "success": True,
            "message": f"Reverted to base model: {self.model}"
        }
    
    def get_current_adapter(self) -> Optional[str]:
        """Get the path of the currently loaded adapter, if any."""
        if hasattr(self, '_current_adapter') and self._current_adapter:
            return self._current_adapter
        return None
    
    def list_available_adapters(self) -> List[Dict[str, Any]]:
        """
        List all available trained adapters.
        
        Returns:
            List of adapter info dicts
        """
        import os
        
        adapters_dir = getattr(Config, 'LOCAL_ADAPTERS_DIR', './adapters')
        adapters = []
        
        if not os.path.exists(adapters_dir):
            return adapters
        
        for name in os.listdir(adapters_dir):
            adapter_path = os.path.join(adapters_dir, name)
            if not os.path.isdir(adapter_path):
                continue
            
            # Check for adapter files
            adapter_config = os.path.join(adapter_path, "adapter_config.json")
            training_config = os.path.join(adapter_path, "training_config.json")
            
            if not (os.path.exists(adapter_config) or os.path.exists(training_config)):
                continue
            
            # Get adapter info
            adapter_info = {
                "name": name,
                "path": adapter_path,
                "has_config": os.path.exists(adapter_config),
                "has_gguf": os.path.exists(os.path.join(adapter_path, "gguf")),
                "is_loaded": (hasattr(self, '_current_adapter') and 
                             self._current_adapter == adapter_path)
            }
            
            # Try to get base model from training config
            if os.path.exists(training_config):
                try:
                    with open(training_config) as f:
                        cfg = json.load(f)
                        adapter_info["base_model"] = cfg.get("model_name", "unknown")
                except Exception:
                    pass
            
            adapters.append(adapter_info)
        
        return adapters
    
    def benchmark_model(
        self,
        prompts: List[str] = None,
        num_runs: int = 3
    ) -> Dict[str, Any]:
        """
        Benchmark the current model configuration.
        
        Args:
            prompts: List of test prompts (uses defaults if None)
            num_runs: Number of runs per prompt for averaging
            
        Returns:
            Benchmark results with timing and quality metrics
        """
        if prompts is None:
            prompts = [
                "Hello, how are you doing today?",
                "What's your favorite thing to do?",
                "Can you tell me something interesting?",
            ]
        
        results = {
            "model": self.model,
            "provider": self.provider,
            "adapter": self.get_current_adapter(),
            "runs": [],
            "avg_latency_ms": 0,
            "avg_tokens_per_second": 0,
        }
        
        system_prompt = "You are a helpful assistant. Keep responses brief."
        total_latency = 0
        total_tokens = 0
        
        for prompt in prompts:
            for run in range(num_runs):
                messages = [{"role": "user", "content": prompt}]
                
                start = time.time()
                try:
                    response = self.generate_response(
                        system_prompt=system_prompt,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=100
                    )
                    latency = (time.time() - start) * 1000  # ms
                    
                    # Rough token count (chars / 4)
                    tokens = len(response) / 4
                    tokens_per_sec = tokens / (latency / 1000) if latency > 0 else 0
                    
                    results["runs"].append({
                        "prompt": prompt[:50] + "...",
                        "latency_ms": round(latency, 2),
                        "response_length": len(response),
                        "tokens_per_second": round(tokens_per_sec, 2)
                    })
                    
                    total_latency += latency
                    total_tokens += tokens_per_sec
                    
                except Exception as e:
                    results["runs"].append({
                        "prompt": prompt[:50] + "...",
                        "error": str(e)
                    })
        
        successful_runs = [r for r in results["runs"] if "error" not in r]
        if successful_runs:
            results["avg_latency_ms"] = round(total_latency / len(successful_runs), 2)
            results["avg_tokens_per_second"] = round(total_tokens / len(successful_runs), 2)
        
        return results
    
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

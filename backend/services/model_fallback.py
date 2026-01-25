"""
Model Fallback System - Automatically switch to backup models when primary fails.
Implements tiered fallback with circuit breaker integration.
"""
import asyncio
from typing import Optional, List, Any, Callable, Dict
from dataclasses import dataclass, field
from enum import Enum

from services.circuit_breaker import circuit_breaker, CircuitOpenError, get_circuit_registry
from services.logger import get_logger

logger = get_logger(__name__)


class ModelTier(Enum):
    """Model tiers for fallback priority."""
    PRIMARY = 1      # Best quality, highest cost
    SECONDARY = 2    # Good quality, medium cost
    FALLBACK = 3     # Basic quality, low cost/local
    EMERGENCY = 4    # Minimal, always available


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    name: str
    tier: ModelTier
    provider: str  # 'google', 'openai', 'anthropic', 'local'
    model_id: str
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout_seconds: float = 30.0
    cost_per_1k_tokens: float = 0.0
    capabilities: List[str] = field(default_factory=list)
    
    def supports(self, capability: str) -> bool:
        return capability in self.capabilities or not self.capabilities


# Default model configurations
DEFAULT_MODELS = [
    ModelConfig(
        name="gemini-pro",
        tier=ModelTier.PRIMARY,
        provider="google",
        model_id="gemini-1.5-pro",
        max_tokens=8192,
        cost_per_1k_tokens=0.00125,
        capabilities=["chat", "code", "reasoning", "long_context"]
    ),
    ModelConfig(
        name="gemini-flash",
        tier=ModelTier.SECONDARY,
        provider="google",
        model_id="gemini-1.5-flash",
        max_tokens=8192,
        cost_per_1k_tokens=0.000075,
        capabilities=["chat", "code", "fast"]
    ),
    ModelConfig(
        name="gpt-4o-mini",
        tier=ModelTier.FALLBACK,
        provider="openai",
        model_id="gpt-4o-mini",
        max_tokens=4096,
        cost_per_1k_tokens=0.00015,
        capabilities=["chat", "code"]
    ),
    ModelConfig(
        name="local-ollama",
        tier=ModelTier.EMERGENCY,
        provider="local",
        model_id="llama3:8b",
        max_tokens=2048,
        cost_per_1k_tokens=0.0,
        capabilities=["chat"]
    ),
]


class ModelFallbackManager:
    """
    Manages model fallback with automatic switching.
    
    Features:
    - Tiered fallback based on model priority
    - Circuit breaker integration
    - Cost tracking
    - Automatic recovery to primary
    """
    
    def __init__(self, models: Optional[List[ModelConfig]] = None):
        self.models = models or DEFAULT_MODELS
        self.models.sort(key=lambda m: m.tier.value)  # Sort by tier
        self._current_model: Optional[ModelConfig] = None
        self._usage_stats: Dict[str, dict] = {}
        self._model_handlers: Dict[str, Callable] = {}
    
    def register_handler(self, provider: str, handler: Callable):
        """
        Register a handler function for a provider.
        
        Handler signature: async def handler(model_id: str, prompt: str, **kwargs) -> str
        """
        self._model_handlers[provider] = handler
    
    def get_current_model(self) -> Optional[ModelConfig]:
        """Get the currently active model."""
        return self._current_model
    
    def get_available_models(self, capability: Optional[str] = None) -> List[ModelConfig]:
        """Get list of available models, optionally filtered by capability."""
        registry = get_circuit_registry()
        available = []
        
        for model in self.models:
            # Check if circuit is open
            circuit_name = f"model:{model.name}"
            try:
                circuit = registry.get_or_create(circuit_name)
                if circuit.state.value == "open":
                    continue
            except:
                pass
            
            # Check capability
            if capability and not model.supports(capability):
                continue
            
            available.append(model)
        
        return available
    
    async def call_with_fallback(
        self,
        prompt: str,
        capability: Optional[str] = None,
        max_retries: int = 3,
        **kwargs
    ) -> tuple[str, ModelConfig]:
        """
        Call a model with automatic fallback on failure.
        
        Returns:
            Tuple of (response, model_used)
        """
        available_models = self.get_available_models(capability)
        
        if not available_models:
            raise RuntimeError("No models available")
        
        last_error = None
        
        for model in available_models:
            circuit_name = f"model:{model.name}"
            
            try:
                logger.info(f"Attempting model: {model.name}")
                
                # Get handler for provider
                handler = self._model_handlers.get(model.provider)
                if not handler:
                    logger.warning(f"No handler for provider: {model.provider}")
                    continue
                
                # Call with circuit breaker
                @circuit_breaker(circuit_name, failure_threshold=3, timeout_seconds=60)
                async def wrapped_call():
                    return await asyncio.wait_for(
                        handler(model.model_id, prompt, **kwargs),
                        timeout=model.timeout_seconds
                    )
                
                response = await wrapped_call()
                
                # Success - record usage
                self._record_usage(model, prompt, response)
                self._current_model = model
                
                return response, model
                
            except CircuitOpenError:
                logger.warning(f"Circuit open for {model.name}, trying next")
                continue
                
            except asyncio.TimeoutError:
                logger.warning(f"Timeout for {model.name}")
                last_error = f"Timeout: {model.name}"
                continue
                
            except Exception as e:
                logger.error(f"Error with {model.name}: {e}")
                last_error = str(e)
                continue
        
        raise RuntimeError(f"All models failed. Last error: {last_error}")
    
    def _record_usage(self, model: ModelConfig, prompt: str, response: str):
        """Record usage statistics for a model."""
        if model.name not in self._usage_stats:
            self._usage_stats[model.name] = {
                "calls": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "estimated_cost": 0.0
            }
        
        stats = self._usage_stats[model.name]
        stats["calls"] += 1
        
        # Rough token estimation (4 chars per token)
        tokens_in = len(prompt) // 4
        tokens_out = len(response) // 4
        
        stats["tokens_in"] += tokens_in
        stats["tokens_out"] += tokens_out
        stats["estimated_cost"] += (tokens_in + tokens_out) / 1000 * model.cost_per_1k_tokens
    
    def get_usage_stats(self) -> dict:
        """Get usage statistics for all models."""
        return {
            "models": self._usage_stats,
            "current_model": self._current_model.name if self._current_model else None,
            "total_cost": sum(s["estimated_cost"] for s in self._usage_stats.values())
        }
    
    def get_health_status(self) -> dict:
        """Get health status of all models."""
        registry = get_circuit_registry()
        status = {}
        
        for model in self.models:
            circuit_name = f"model:{model.name}"
            try:
                circuit = registry.get_or_create(circuit_name)
                status[model.name] = {
                    "tier": model.tier.value,
                    "provider": model.provider,
                    "circuit_state": circuit.state.value,
                    "available": circuit.state.value != "open"
                }
            except:
                status[model.name] = {
                    "tier": model.tier.value,
                    "provider": model.provider,
                    "circuit_state": "unknown",
                    "available": True
                }
        
        return status


# ============= Singleton =============

_manager: Optional[ModelFallbackManager] = None


    def register_default_handlers(self):
        """Register default handlers for known providers."""
        from services.llm_service import get_llm_service
        from services.ollama_service import get_ollama_service
        import logging
        
        logger = logging.getLogger(__name__)

        async def google_handler(model_id: str, prompt: str, **kwargs) -> str:
            # Bridging to existing LLMService for now, or use google-generativeai directly
            # For consistency, we'll use LLMService's method but forced to specific model
            # Note: LLMService is sync, so we might need running in threadpool if async required
            # checking LLMService... it is sync.
            import asyncio
            return await asyncio.to_thread(
                get_llm_service().generate_response, 
                system_prompt="You are a helpful assistant.", 
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get('max_tokens'),
                temperature=kwargs.get('temperature')
            )

        async def openai_handler(model_id: str, prompt: str, **kwargs) -> str:
            # Similar bridge for OpenAI
            import asyncio
            llm = get_llm_service()
            # Temporarily force provider to openai to use its logic, or use fallback_client directly
            # Easier to use the fallback logic if available
            if llm.fallback_client:
                return await asyncio.to_thread(
                    llm._openai_fallback_generate,
                    system_prompt="You are a helpful assistant.",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get('temperature', 0.7),
                    max_tokens=kwargs.get('max_tokens', 1024)
                )
            raise RuntimeError("OpenAI client not initialized")

        async def locall_handler(model_id: str, prompt: str, **kwargs) -> str:
            # Use new OllamaService
             return get_ollama_service().generate_chat(
                messages=[{"role": "user", "content": prompt}],
                model=model_id,
                temperature=kwargs.get('temperature', 0.7),
                max_tokens=kwargs.get('max_tokens', 2048)
            )

        self.register_handler("google", google_handler)
        self.register_handler("openai", openai_handler)
        self.register_handler("local", locall_handler)
        self.register_handler("ollama", locall_handler)  # Alias
        logger.info("Registered default model handlers (google, openai, local)")

    
def get_model_manager() -> ModelFallbackManager:
    global _manager
    if _manager is None:
        _manager = ModelFallbackManager()
        _manager.register_default_handlers()
    return _manager

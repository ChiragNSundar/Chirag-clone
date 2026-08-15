"""
Model Fallback System - Manages LM Studio model availability.
If LM Studio is down, the system falls back to RAG + context files.

No cloud providers. No Ollama. LM Studio is the sole LLM.
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
    PRIMARY = 1      # LM Studio loaded model
    FALLBACK = 2     # RAG + context files (no LLM)


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    name: str
    tier: ModelTier
    provider: str  # 'lmstudio' or 'rag'
    model_id: str
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout_seconds: float = 120.0
    cost_per_1k_tokens: float = 0.0  # Always 0 — local only
    capabilities: List[str] = field(default_factory=list)
    
    def supports(self, capability: str) -> bool:
        return capability in self.capabilities or not self.capabilities


# Default model configurations — LM Studio only
DEFAULT_MODELS = [
    ModelConfig(
        name="lmstudio-primary",
        tier=ModelTier.PRIMARY,
        provider="lmstudio",
        model_id="auto",  # Auto-detect from LM Studio
        max_tokens=4096,
        cost_per_1k_tokens=0.0,
        capabilities=["chat", "code", "reasoning"]
    ),
    ModelConfig(
        name="rag-fallback",
        tier=ModelTier.FALLBACK,
        provider="rag",
        model_id="context-files",
        max_tokens=0,  # No generation — retrieval only
        cost_per_1k_tokens=0.0,
        capabilities=["chat"]
    ),
]


class ModelFallbackManager:
    """
    Manages model fallback with automatic switching.
    
    Features:
    - LM Studio as primary (auto-detect loaded model)
    - RAG + context files as fallback when LLM is unavailable
    - Circuit breaker integration
    - Usage tracking
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
        max_retries: int = 2,
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
        # Cost is always 0 for local models
    
    def get_usage_stats(self) -> dict:
        """Get usage statistics for all models."""
        return {
            "models": self._usage_stats,
            "current_model": self._current_model.name if self._current_model else None,
            "total_cost": 0.0  # Always free — local only
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

    def register_default_handlers(self):
        """Register default handlers for known providers."""
        from services.llm_service import get_llm_service

        async def lmstudio_handler(model_id: str, prompt: str, **kwargs) -> str:
            """Handler for LM Studio via LLMService."""
            return await asyncio.to_thread(
                get_llm_service().generate_response,
                system_prompt="You are a helpful assistant.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get('max_tokens'),
                temperature=kwargs.get('temperature')
            )

        async def rag_handler(model_id: str, prompt: str, **kwargs) -> str:
            """Handler for RAG-only fallback (no LLM generation)."""
            try:
                from services.context_service import get_context_service
                ctx = get_context_service()
                relevant = ctx.get_relevant_context(prompt, top_k=5)
                if relevant:
                    return (
                        "Based on my knowledge base:\n\n" +
                        "\n\n".join(relevant)
                    )
            except Exception:
                pass
            return "I'm currently in knowledge-base only mode. Please start LM Studio for full AI responses."

        self.register_handler("lmstudio", lmstudio_handler)
        self.register_handler("rag", rag_handler)
        logger.info("Registered model handlers (lmstudio, rag)")


# ============= Singleton =============

_manager: Optional[ModelFallbackManager] = None


def get_model_manager() -> ModelFallbackManager:
    global _manager
    if _manager is None:
        _manager = ModelFallbackManager()
        _manager.register_default_handlers()
    return _manager

"""
Telemetry Configuration - OpenTelemetry setup for tracing.
Degrades gracefully if opentelemetry packages are not installed.
"""
from config import Config
from services.logger import get_logger

logger = get_logger(__name__)

try:
    from opentelemetry import trace  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.resources import Resource  # type: ignore
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore
    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False


def setup_telemetry(app):
    """Setup OpenTelemetry tracing for the FastAPI application."""
    if not HAS_OTEL:
        logger.info("OpenTelemetry not installed — tracing disabled")
        return None
    
    try:
        resource = Resource.create({
            "service.name": "chirag-clone-backend",
            "service.version": "3.1.0",
            "deployment.environment": "production" if not Config.DEBUG else "development"
        })
        
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        
        return trace.get_tracer(__name__)
    except Exception as e:
        logger.warning(f"Telemetry setup warning: {e}")
        return None


def instrument_method(tracer=None, span_name=None):
    """Decorator to instrument a specific method."""
    def decorator(func):
        from functools import wraps
        @wraps(func)
        def wrapper(*args, **kwargs):
            if HAS_OTEL and tracer:
                name = span_name or func.__name__
                with tracer.start_as_current_span(name):
                    return func(*args, **kwargs)
            return func(*args, **kwargs)
        return wrapper
    return decorator

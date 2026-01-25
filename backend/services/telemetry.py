"""
Telemetry Configuration - OpenTelemetry setup for tracing.
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from config import Config

def setup_telemetry(app):
    """Setup OpenTelemetry tracing for the FastAPI application."""
    
    # Define resource (service name, version, etc)
    resource = Resource.create({
        "service.name": "chirag-clone-backend",
        "service.version": "3.0.0",
        "deployment.environment": "production" if not Config.DEBUG else "development"
    })
    
    # Set up the tracer provider
    provider = TracerProvider(resource=resource)
    
    # For now, we'll use Console exporter in dev, but set up structure for Jaeger/OTLP
    # In production, you'd typically swap this for OTLPSpanExporter
    if Config.DEBUG:
         # Export traces to console (useful for debugging, maybe noisy)
         # processor = BatchSpanProcessor(ConsoleSpanExporter())
         # provider.add_span_processor(processor)
         pass # disabling console export by default to avoid noise, enable if needed
    
    # We can add a NoOp span processor if we don't want to export anywhere yet
    # but still want the instrumentation to work (so code doesn't break)
    
    trace.set_tracer_provider(provider)
    
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    
    return trace.get_tracer(__name__)

def instrument_method(tracer, span_name=None):
    """Decorator to instrument a specific method."""
    def decorator(func):
        from functools import wraps
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = span_name or func.__name__
            with tracer.start_as_current_span(name):
                return func(*args, **kwargs)
        return wrapper
    return decorator

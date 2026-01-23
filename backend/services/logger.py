"""
Structured Logging Service using structlog.
Provides JSON logging in production and colored console logging in development.
"""
import logging
import sys
import structlog
from config import Config

def configure_logger():
    """Configure structured logging."""
    
    # Processors applied to all loggers
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Renderer based on environment
    if Config.DEBUG:
        # Development: Colored console output
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # Production: JSON output
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Configure standard library logging to use structlog formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(Config.LOG_LEVEL)

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name=None):
    """Get a structured logger."""
    return structlog.get_logger(name)

# Auto-configure on import
try:
    configure_logger()
except Exception as e:
    # Fallback if configuration fails (e.g. during circular imports or testing)
    print(f"Logging config failed: {e}")

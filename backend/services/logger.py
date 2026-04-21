"""
Structured Logging Service using structlog.
Provides JSON logging in production and colored console logging in development.
"""
import logging
import sys
import structlog
from config import Config

def configure_logger():
    """Configure structured logging.
    
    Uses PrintLoggerFactory with UTF-8 stdout to handle emoji on Windows
    and avoid Python 3.14 stdlib logging incompatibilities.
    """
    
    # Force UTF-8 stdout on Windows to handle emoji in log messages
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass  # reconfigure not available in all environments

    # Renderer based on environment
    if Config.DEBUG:
        # Development: Colored console output
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # Production: JSON output
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Silence noisy stdlib loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name=None):
    """Get a structured logger."""
    return structlog.get_logger(name)

# Auto-configure on import
try:
    configure_logger()
except Exception as e:
    # Fallback if configuration fails (e.g. during circular imports or testing)
    print(f"Logging config failed: {e}")

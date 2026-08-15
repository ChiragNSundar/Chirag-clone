"""
Structured Logging Service using structlog with standard logging fallback.
Provides JSON logging in production and colored console logging in development.
"""
import logging
import sys

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False

from config import Config

def configure_logger():
    """Configure structured logging."""
    if not HAS_STRUCTLOG:
        logging.basicConfig(
            level=Config.LOG_LEVEL,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        return

    # Force UTF-8 stdout on Windows to handle emoji in log messages
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    # Renderer based on environment
    if Config.DEBUG:
        renderer = structlog.dev.ConsoleRenderer()
    else:
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
    """Get a logger instance."""
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name or "app")

# Auto-configure on import
try:
    configure_logger()
except Exception as e:
    print(f"Logging config failed: {e}")

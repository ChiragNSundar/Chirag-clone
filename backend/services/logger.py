"""
Logger Service - Centralized logging configuration with structured output.
Framework-agnostic implementation (works with Flask, FastAPI, or standalone).
"""
import logging
import sys
import uuid
from datetime import datetime
from functools import wraps
import time
import threading

# Thread-local storage for request context (framework-agnostic)
_request_context = threading.local()


def set_request_id(request_id: str = None):
    """Set request ID for current thread."""
    _request_context.request_id = request_id or str(uuid.uuid4())[:8]


def get_request_id() -> str:
    """Get request ID for current thread."""
    return getattr(_request_context, 'request_id', 'N/A')


class RequestIdFilter(logging.Filter):
    """Add request ID to log records."""
    
    def filter(self, record):
        record.request_id = get_request_id()
        return True


def setup_logging(app=None, level=logging.INFO):
    """
    Configure centralized logging for the application.
    
    Args:
        app: Application instance (optional, for backwards compatibility)
        level: Logging level
    """
    # Create formatter with request ID
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)7s | %(request_id)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RequestIdFilter())
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = []  # Clear existing handlers
    root_logger.addHandler(console_handler)
    
    # Configure app-specific loggers
    app_loggers = [
        'services.chat_service',
        'services.llm_service',
        'services.memory_service',
        'services.personality_service',
        'services.search_service',
        'services.vision_service',
        'routes',
        'werkzeug'
    ]
    
    for logger_name in app_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.addHandler(console_handler)
        logger.propagate = False
    
    # Reduce noise from third-party libraries
    logging.getLogger('chromadb').setLevel(logging.WARNING)
    logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)7s | %(request_id)s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)
    return logger


def request_logging_middleware(app):
    """
    Add request logging middleware (Legacy Flask support).
    For FastAPI, use middleware defined in main.py instead.
    
    Logs:
    - Incoming requests with method, path, client IP
    - Response status and duration
    - Slow requests (>2 seconds)
    """
    logger = get_logger('http')
    
    @app.before_request
    def before_request():
        g.request_id = str(uuid.uuid4())[:8]
        g.start_time = time.time()
        
        # Skip logging for static files
        if not request.path.startswith('/api/'):
            return
        
        logger.info(f"REQ → {request.method} {request.path} from {request.remote_addr}")
    
    @app.after_request
    def after_request(response):
        # Skip logging for static files
        if not request.path.startswith('/api/'):
            return response
        
        duration = (time.time() - getattr(g, 'start_time', time.time())) * 1000
        
        log_msg = f"RES ← {response.status_code} in {duration:.0f}ms"
        
        if duration > 2000:
            logger.warning(f"{log_msg} [SLOW REQUEST]")
        elif response.status_code >= 500:
            logger.error(log_msg)
        elif response.status_code >= 400:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        
        return response
    
    return app


def log_execution_time(func):
    """Decorator to log function execution time."""
    logger = get_logger(func.__module__)
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = (time.time() - start) * 1000
            if duration > 1000:
                logger.warning(f"{func.__name__} took {duration:.0f}ms")
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"{func.__name__} failed after {duration:.0f}ms: {e}")
            raise
    
    return wrapper

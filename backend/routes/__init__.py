"""
Routes package initialization.
"""
from .chat_routes import chat_bp
from .training_routes import training_bp
from .upload_routes import upload_bp
from .visualization_routes import visualization_bp
from .autopilot_routes import autopilot_bp
from .timeline_routes import timeline_bp
from .analytics_routes import analytics_bp
from .knowledge_routes import knowledge_bp
from .proactive_routes import proactive_bp

__all__ = [
    'chat_bp', 'training_bp', 'upload_bp', 'visualization_bp',
    'autopilot_bp', 'timeline_bp', 'analytics_bp', 'knowledge_bp', 'proactive_bp'
]


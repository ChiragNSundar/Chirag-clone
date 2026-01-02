"""
Chat Routes - API endpoints for chat functionality.
Enhanced with rate limiting, input validation, and vision support.
"""
from flask import Blueprint, request, jsonify
from services.chat_service import get_chat_service
from services.personality_service import get_personality_service
from services.vision_service import get_vision_service
from services.rate_limiter import rate_limit
from services.logger import get_logger
from config import Config
import uuid
import re

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')
logger = get_logger(__name__)

# Input validation constants
MAX_MESSAGE_LENGTH = getattr(Config, 'MAX_MESSAGE_LENGTH', 10000)
MAX_SESSION_ID_LENGTH = 100
SESSION_ID_PATTERN = re.compile(r'^[a-zA-Z0-9\-_]+$')


def validate_session_id(session_id: str) -> tuple:
    """
    Validate session ID format.
    Returns (is_valid, error_message or None)
    """
    if not session_id:
        return True, None  # Empty is OK, will generate new
    
    if len(session_id) > MAX_SESSION_ID_LENGTH:
        return False, f'Session ID too long (max {MAX_SESSION_ID_LENGTH} characters)'
    
    if not SESSION_ID_PATTERN.match(session_id):
        return False, 'Session ID contains invalid characters'
    
    return True, None


def sanitize_message(message: str) -> str:
    """Sanitize message content by removing control characters."""
    if not message:
        return ''
    # Remove null bytes and other control characters except newlines/tabs
    return ''.join(char for char in message if char >= ' ' or char in '\n\t\r')


@chat_bp.route('/message', methods=['POST'])
@rate_limit
def send_message():
    """
    Send a message and get a response.
    
    Request body:
    {
        "message": "Hello!",
        "session_id": "optional-session-id",
        "image": "optional-base64-image-data",
        "image_type": "image/jpeg"
    }
    """
    # Get JSON data
    try:
        data = request.get_json()
    except Exception as e:
        logger.warning(f"Invalid JSON in request: {e}")
        return jsonify({'error': 'Invalid JSON in request body'}), 400
    
    if not data or 'message' not in data:
        return jsonify({'error': 'Message is required'}), 400
    
    # Validate and sanitize message
    raw_message = data.get('message', '')
    if not isinstance(raw_message, str):
        return jsonify({'error': 'Message must be a string'}), 400
    
    message = sanitize_message(raw_message).strip()
    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({'error': f'Message too long (max {MAX_MESSAGE_LENGTH} characters)'}), 400
    
    # Validate session ID
    session_id = data.get('session_id', '')
    if session_id:
        is_valid, error = validate_session_id(session_id)
        if not is_valid:
            return jsonify({'error': error}), 400
    else:
        session_id = str(uuid.uuid4())
    
    training_mode = bool(data.get('training_mode', False))
    image_data = data.get('image')
    image_type = data.get('image_type', 'image/jpeg')
    
    # Validate image type if provided
    if image_data:
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if image_type not in allowed_types:
            image_type = 'image/jpeg'  # Default to jpeg
        
        # Validate image size (rough check - base64 is ~1.33x larger)
        if len(image_data) > 10 * 1024 * 1024:  # ~7.5MB actual image
            return jsonify({'error': 'Image too large (max 7.5MB)'}), 400
    
    # If image is provided, analyze it and add context to message
    image_context = None
    if image_data and not training_mode:
        try:
            vision = get_vision_service()
            if vision.is_available():
                result = vision.react_to_image(
                    image_data=image_data,
                    user_message=message,
                    personality_context="Respond naturally as the user's clone.",
                    mime_type=image_type
                )
                if result['success']:
                    # Use vision response directly
                    return jsonify({
                        'response': result['reaction'],
                        'session_id': session_id,
                        'confidence': 85,
                        'mood': None,
                        'has_image': True
                    })
        except Exception as e:
            logger.warning(f"Vision error: {e}")
            image_context = "[Image attached but could not be analyzed]"
    
    try:
        chat_service = get_chat_service()
        
        # Include image context in message if vision failed
        full_message = message
        if image_context:
            full_message = f"{message}\n\n{image_context}"
        
        response, confidence, mood = chat_service.generate_response(full_message, session_id, training_mode=training_mode)
        
        return jsonify({
            'response': response,
            'session_id': session_id,
            'confidence': round(confidence * 100),
            'mood': mood
        })
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Chat error: {error_msg}")
        
        # Provide helpful error messages without exposing internals
        if 'API key' in error_msg or 'GEMINI_API_KEY' in error_msg:
            return jsonify({
                'error': 'API key not configured. Please set GEMINI_API_KEY in your .env file.',
                'response': 'I cannot respond right now - the API key is not configured.'
            }), 200  # Return 200 so frontend shows the message
        elif 'proxies' in error_msg:
            return jsonify({
                'error': 'Library version conflict. Please reinstall dependencies.',
                'response': 'There is a configuration issue. Please restart the server.'
            }), 200
        elif 'rate limit' in error_msg.lower() or 'quota' in error_msg.lower():
            return jsonify({
                'error': 'API rate limit reached. Please try again in a few minutes.',
                'response': 'I need a short break. Please try again in a minute.'
            }), 200
        else:
            return jsonify({
                'error': 'An error occurred',
                'response': 'Sorry, I encountered an error. Please try again.'
            }), 200


@chat_bp.route('/history/<session_id>', methods=['GET'])
@rate_limit
def get_history(session_id: str):
    """Get conversation history for a session."""
    # Validate session ID
    is_valid, error = validate_session_id(session_id)
    if not is_valid:
        return jsonify({'error': error}), 400
    
    try:
        from services.memory_service import get_memory_service
        memory = get_memory_service()
        
        history = memory.get_conversation_history(session_id)
        
        return jsonify({
            'session_id': session_id,
            'messages': history
        })
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return jsonify({'error': 'Failed to get conversation history'}), 500


@chat_bp.route('/new-session', methods=['POST'])
@rate_limit
def new_session():
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    return jsonify({'session_id': session_id})


@chat_bp.route('/personality', methods=['GET'])
@rate_limit
def get_personality():
    """Get the current personality profile."""
    try:
        personality = get_personality_service()
        profile = personality.get_profile()
        
        return jsonify({
            'name': profile.name,
            'typing_quirks': profile.typing_quirks,
            'emoji_patterns': profile.emoji_patterns,
            'tone_markers': profile.tone_markers,
            'facts': profile.facts,
            'avg_message_length': profile.avg_message_length,
            'example_count': len(profile.response_examples)
        })
    except Exception as e:
        logger.error(f"Error getting personality: {e}")
        return jsonify({'error': 'Failed to get personality profile'}), 500


@chat_bp.route('/personality/name', methods=['PUT'])
@rate_limit
def update_name():
    """Update the bot's name."""
    try:
        data = request.get_json()
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Name is required'}), 400
    
    name = data['name']
    if not isinstance(name, str) or not name.strip():
        return jsonify({'error': 'Name must be a non-empty string'}), 400
    
    if len(name) > 50:
        return jsonify({'error': 'Name too long (max 50 characters)'}), 400
    
    # Sanitize name
    name = sanitize_message(name).strip()
    
    try:
        personality = get_personality_service()
        personality.update_name(name)
        
        return jsonify({'success': True, 'name': name})
    except Exception as e:
        logger.error(f"Error updating name: {e}")
        return jsonify({'error': 'Failed to update name'}), 500


@chat_bp.route('/stats', methods=['GET'])
@rate_limit
def get_stats():
    """Get training statistics."""
    try:
        chat_service = get_chat_service()
        stats = chat_service.get_training_stats()
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': 'Failed to get statistics'}), 500

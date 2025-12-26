"""
Chat Routes - API endpoints for chat functionality.
Now supports vision (image) inputs.
"""
from flask import Blueprint, request, jsonify
from services.chat_service import get_chat_service
from services.personality_service import get_personality_service
from services.vision_service import get_vision_service
import uuid

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')


@chat_bp.route('/message', methods=['POST'])
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
    data = request.get_json()
    
    if not data or 'message' not in data:
        return jsonify({'error': 'Message is required'}), 400
    
    message = data['message'].strip()
    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    session_id = data.get('session_id', str(uuid.uuid4()))
    training_mode = data.get('training_mode', False)
    image_data = data.get('image')
    image_type = data.get('image_type', 'image/jpeg')
    
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
            print(f"Vision error: {e}")
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
        print(f"Chat error: {error_msg}")
        
        # Provide helpful error messages
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
        else:
            return jsonify({
                'error': error_msg,
                'response': f'Sorry, I encountered an error: {error_msg}'
            }), 200


@chat_bp.route('/history/<session_id>', methods=['GET'])
def get_history(session_id: str):
    """Get conversation history for a session."""
    try:
        from services.memory_service import get_memory_service
        memory = get_memory_service()
        
        history = memory.get_conversation_history(session_id)
        
        return jsonify({
            'session_id': session_id,
            'messages': history
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/new-session', methods=['POST'])
def new_session():
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    return jsonify({'session_id': session_id})


@chat_bp.route('/personality', methods=['GET'])
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
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/personality/name', methods=['PUT'])
def update_name():
    """Update the bot's name."""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Name is required'}), 400
    
    try:
        personality = get_personality_service()
        personality.update_name(data['name'])
        
        return jsonify({'success': True, 'name': data['name']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get training statistics."""
    try:
        chat_service = get_chat_service()
        stats = chat_service.get_training_stats()
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

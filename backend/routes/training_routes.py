"""
Training Routes - API endpoints for the training corner.
Enhanced with rate limiting and input validation.
"""
from flask import Blueprint, request, jsonify
from services.chat_service import get_chat_service
from services.personality_service import get_personality_service
from services.memory_service import get_memory_service
from services.rate_limiter import rate_limit
from services.logger import get_logger

training_bp = Blueprint('training', __name__, url_prefix='/api/training')
logger = get_logger(__name__)

# Validation constants
MAX_CONTEXT_LENGTH = 5000
MAX_RESPONSE_LENGTH = 5000
MAX_FACT_LENGTH = 500


def sanitize_text(text: str) -> str:
    """Remove control characters from text."""
    if not text:
        return ''
    return ''.join(char for char in text if char >= ' ' or char in '\n\t\r')


@training_bp.route('/feedback', methods=['POST'])
@rate_limit
def submit_feedback():
    """
    Submit feedback on a bot response for training.
    
    Request body:
    {
        "context": "The message that was sent",
        "bot_response": "What the bot said",
        "correct_response": "What you would have said",
        "accepted": false
    }
    """
    try:
        data = request.get_json()
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    context = sanitize_text(data.get('context', '')).strip()
    correct_response = sanitize_text(data.get('correct_response', '')).strip()
    accepted = bool(data.get('accepted', False))
    
    if not context:
        return jsonify({'error': 'Context is required'}), 400
    
    if len(context) > MAX_CONTEXT_LENGTH:
        return jsonify({'error': f'Context too long (max {MAX_CONTEXT_LENGTH} characters)'}), 400
    
    if correct_response and len(correct_response) > MAX_RESPONSE_LENGTH:
        return jsonify({'error': f'Response too long (max {MAX_RESPONSE_LENGTH} characters)'}), 400
    
    try:
        chat_service = get_chat_service()
        
        if accepted:
            # If accepted, use the bot's response as training
            bot_response = sanitize_text(data.get('bot_response', '')).strip()
            if bot_response:
                if len(bot_response) > MAX_RESPONSE_LENGTH:
                    return jsonify({'error': f'Bot response too long (max {MAX_RESPONSE_LENGTH} characters)'}), 400
                chat_service.train_from_interaction(context, bot_response)
        else:
            # If rejected, use the correct response
            if not correct_response:
                return jsonify({'error': 'Correct response is required when rejecting'}), 400
            chat_service.train_from_interaction(context, correct_response)
        
        return jsonify({
            'success': True,
            'message': 'Training data saved'
        })
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        return jsonify({'error': 'Failed to save feedback'}), 500


@training_bp.route('/example', methods=['POST'])
@rate_limit
def add_example():
    """
    Add a direct training example.
    
    Request body:
    {
        "context": "What someone said to you",
        "response": "How you responded"
    }
    """
    try:
        data = request.get_json()
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    context = sanitize_text(data.get('context', '')).strip()
    response = sanitize_text(data.get('response', '')).strip()
    
    if not context or not response:
        return jsonify({'error': 'Both context and response are required'}), 400
    
    if len(context) > MAX_CONTEXT_LENGTH:
        return jsonify({'error': f'Context too long (max {MAX_CONTEXT_LENGTH} characters)'}), 400
    
    if len(response) > MAX_RESPONSE_LENGTH:
        return jsonify({'error': f'Response too long (max {MAX_RESPONSE_LENGTH} characters)'}), 400
    
    try:
        memory = get_memory_service()
        memory.add_training_example(context, response, source='manual')
        
        personality = get_personality_service()
        personality.add_example(context, response)
        
        return jsonify({
            'success': True,
            'message': 'Example added'
        })
    except Exception as e:
        logger.error(f"Add example error: {e}")
        return jsonify({'error': 'Failed to add example'}), 500


@training_bp.route('/fact', methods=['POST'])
@rate_limit
def add_fact():
    """
    Add a personal fact about yourself.
    
    Request body:
    {
        "fact": "I love playing guitar"
    }
    """
    try:
        data = request.get_json()
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400
    
    if not data or 'fact' not in data:
        return jsonify({'error': 'Fact is required'}), 400
    
    fact = sanitize_text(data['fact']).strip()
    if not fact:
        return jsonify({'error': 'Fact cannot be empty'}), 400
    
    if len(fact) > MAX_FACT_LENGTH:
        return jsonify({'error': f'Fact too long (max {MAX_FACT_LENGTH} characters)'}), 400
    
    try:
        personality = get_personality_service()
        personality.add_fact(fact)
        
        return jsonify({
            'success': True,
            'message': 'Fact added',
            'facts': personality.get_profile().facts
        })
    except Exception as e:
        logger.error(f"Add fact error: {e}")
        return jsonify({'error': 'Failed to add fact'}), 500


@training_bp.route('/facts', methods=['GET'])
@rate_limit
def get_facts():
    """Get all stored facts."""
    try:
        personality = get_personality_service()
        return jsonify({
            'facts': personality.get_profile().facts
        })
    except Exception as e:
        logger.error(f"Get facts error: {e}")
        return jsonify({'error': 'Failed to get facts'}), 500


@training_bp.route('/facts/<int:index>', methods=['DELETE'])
@rate_limit
def delete_fact(index: int):
    """Delete a fact by index."""
    # Validate index
    if index < 0 or index > 1000:
        return jsonify({'error': 'Invalid fact index'}), 400
    
    try:
        personality = get_personality_service()
        facts = personality.get_profile().facts
        
        if 0 <= index < len(facts):
            facts.pop(index)
            personality.save_profile()
            return jsonify({'success': True, 'facts': facts})
        else:
            return jsonify({'error': 'Fact index out of range'}), 400
    except Exception as e:
        logger.error(f"Delete fact error: {e}")
        return jsonify({'error': 'Failed to delete fact'}), 500


@training_bp.route('/clear', methods=['DELETE'])
@rate_limit
def clear_training():
    """Clear all training data (use with caution!)."""
    try:
        memory = get_memory_service()
        memory.clear_training_data()
        
        logger.warning("Training data cleared by user request")
        
        return jsonify({
            'success': True,
            'message': 'Training data cleared'
        })
    except Exception as e:
        logger.error(f"Clear training error: {e}")
        return jsonify({'error': 'Failed to clear training data'}), 500


@training_bp.route('/stats', methods=['GET'])
@rate_limit
def get_training_stats():
    """Get training statistics."""
    try:
        memory = get_memory_service()
        personality = get_personality_service()
        
        stats = memory.get_training_stats()
        profile = personality.get_profile()
        
        return jsonify({
            'total_examples': stats.get('total_examples', 0),
            'sources': stats.get('sources', {}),
            'facts_count': len(profile.facts),
            'quirks_count': len(profile.typing_quirks),
            'example_responses': len(profile.response_examples)
        })
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        return jsonify({'error': 'Failed to get statistics'}), 500

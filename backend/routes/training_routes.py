"""
Training Routes - API endpoints for the training corner.
"""
from flask import Blueprint, request, jsonify
from services.chat_service import get_chat_service
from services.personality_service import get_personality_service
from services.memory_service import get_memory_service

training_bp = Blueprint('training', __name__, url_prefix='/api/training')


@training_bp.route('/feedback', methods=['POST'])
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
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    context = data.get('context', '')
    correct_response = data.get('correct_response', '')
    accepted = data.get('accepted', False)
    
    if not context:
        return jsonify({'error': 'Context is required'}), 400
    
    try:
        chat_service = get_chat_service()
        
        if accepted:
            # If accepted, use the bot's response as training
            bot_response = data.get('bot_response', '')
            if bot_response:
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
        return jsonify({'error': str(e)}), 500


@training_bp.route('/example', methods=['POST'])
def add_example():
    """
    Add a direct training example.
    
    Request body:
    {
        "context": "What someone said to you",
        "response": "How you responded"
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    context = data.get('context', '').strip()
    response = data.get('response', '').strip()
    
    if not context or not response:
        return jsonify({'error': 'Both context and response are required'}), 400
    
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
        return jsonify({'error': str(e)}), 500


@training_bp.route('/fact', methods=['POST'])
def add_fact():
    """
    Add a personal fact about yourself.
    
    Request body:
    {
        "fact": "I love playing guitar"
    }
    """
    data = request.get_json()
    
    if not data or 'fact' not in data:
        return jsonify({'error': 'Fact is required'}), 400
    
    fact = data['fact'].strip()
    if not fact:
        return jsonify({'error': 'Fact cannot be empty'}), 400
    
    try:
        personality = get_personality_service()
        personality.add_fact(fact)
        
        return jsonify({
            'success': True,
            'message': 'Fact added',
            'facts': personality.get_profile().facts
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@training_bp.route('/facts', methods=['GET'])
def get_facts():
    """Get all stored facts."""
    try:
        personality = get_personality_service()
        return jsonify({
            'facts': personality.get_profile().facts
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@training_bp.route('/facts/<int:index>', methods=['DELETE'])
def delete_fact(index: int):
    """Delete a fact by index."""
    try:
        personality = get_personality_service()
        facts = personality.get_profile().facts
        
        if 0 <= index < len(facts):
            facts.pop(index)
            personality.save_profile()
            return jsonify({'success': True, 'facts': facts})
        else:
            return jsonify({'error': 'Invalid fact index'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@training_bp.route('/clear', methods=['DELETE'])
def clear_training():
    """Clear all training data (use with caution!)."""
    try:
        memory = get_memory_service()
        memory.clear_training_data()
        
        return jsonify({
            'success': True,
            'message': 'Training data cleared'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@training_bp.route('/stats', methods=['GET'])
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
        return jsonify({'error': str(e)}), 500

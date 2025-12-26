"""
Visualization Routes - API endpoints for personality visualization data.
"""
from flask import Blueprint, jsonify
from services.personality_service import get_personality_service
from services.memory_service import get_memory_service
from collections import Counter
import re

visualization_bp = Blueprint('visualization', __name__, url_prefix='/api/visualization')

# Common stop words to filter out from word cloud
STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
    'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
    'shall', 'can', 'need', 'dare', 'ought', 'used', 'it', 'its', 'this', 'that',
    'these', 'those', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves',
    'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself',
    'she', 'her', 'hers', 'herself', 'they', 'them', 'their', 'theirs', 'themselves',
    'what', 'which', 'who', 'whom', 'when', 'where', 'why', 'how', 'all', 'each',
    'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
    'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also',
    'now', 'here', 'there', 'then', 'once', 'if', 'because', 'until', 'while',
    'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'any', 'both',
    'im', 'dont', 'cant', 'wont', 'didnt', 'isnt', 'arent', 'wasnt', 'werent',
    'hasnt', 'havent', 'hadnt', 'doesnt', 'wouldnt', 'couldnt', 'shouldnt',
    'gonna', 'wanna', 'gotta', 'yeah', 'yes', 'no', 'ok', 'okay', 'like', 'just',
    'really', 'actually', 'basically', 'literally', 'thing', 'things', 'something',
    'anything', 'everything', 'nothing', 'someone', 'anyone', 'everyone', 'get', 'got',
    'know', 'think', 'make', 'go', 'see', 'come', 'take', 'want', 'look', 'use',
    'find', 'give', 'tell', 'work', 'call', 'try', 'ask', 'feel', 'seem', 'leave',
    'put', 'mean', 'keep', 'let', 'begin', 'show', 'hear', 'play', 'run', 'move',
    'say', 'said', 'says', 'one', 'two', 'way', 'even', 'new', 'good', 'first',
    'last', 'long', 'great', 'little', 'own', 'old', 'right', 'big', 'high',
    'different', 'small', 'large', 'next', 'early', 'young', 'important', 'public',
    'still', 'back', 'well', 'much', 'ever', 'never', 'always', 'kind', 'maybe',
    'sure', 'ur', 'u', 'r', 'b', 'k', 'n', 'm', 'd', 's', 't', 'w', 'c', 'p',
}


@visualization_bp.route('/data', methods=['GET'])
def get_visualization_data():
    """Get all visualization data for the Brain Map."""
    try:
        personality = get_personality_service()
        memory = get_memory_service()
        profile = personality.get_profile()
        
        # 1. Radar Chart Data - Personality Traits
        radar_data = {
            'labels': ['Casual', 'Formal', 'Enthusiastic', 'Sarcastic', 'Brief'],
            'values': [
                round(profile.tone_markers.get('casual', 0.5) * 100),
                round(profile.tone_markers.get('formal', 0.5) * 100),
                round(profile.tone_markers.get('enthusiastic', 0.5) * 100),
                round(profile.tone_markers.get('sarcastic', 0) * 100),
                round(profile.tone_markers.get('brief', 0.5) * 100),
            ]
        }
        
        # 2. Word Cloud Data - Most used words
        word_freq = {}
        if profile.vocabulary:
            for word, count in profile.vocabulary.items():
                word_lower = word.lower()
                if (word_lower not in STOP_WORDS and 
                    len(word_lower) > 2 and 
                    word_lower.isalpha()):
                    word_freq[word_lower] = count
        
        # Get top 50 words for word cloud
        word_cloud = [
            {'text': word, 'size': min(count * 2, 100)}
            for word, count in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:50]
        ]
        
        # 3. Emoji Usage
        emoji_data = [
            {'emoji': emoji, 'count': count}
            for emoji, count in sorted(profile.emoji_patterns.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # 4. Typing Quirks
        quirks = profile.typing_quirks[:15]
        
        # 5. Statistics
        stats = memory.get_training_stats()
        stats_data = {
            'total_examples': stats.get('total_examples', 0),
            'facts_count': len(profile.facts),
            'quirks_count': len(profile.typing_quirks),
            'avg_message_length': round(profile.avg_message_length, 1),
            'vocabulary_size': len(profile.vocabulary),
        }
        
        # 6. Learning Progress - source breakdown
        sources = stats.get('sources', {})
        source_data = [
            {'source': source, 'count': count}
            for source, count in sources.items()
        ]
        
        return jsonify({
            'radar': radar_data,
            'wordCloud': word_cloud,
            'emojis': emoji_data,
            'quirks': quirks,
            'stats': stats_data,
            'sources': source_data
        })
        
    except Exception as e:
        print(f"Visualization error: {e}")
        return jsonify({'error': str(e)}), 500


@visualization_bp.route('/traits', methods=['GET'])
def get_traits():
    """Get just the personality traits for the radar chart."""
    try:
        personality = get_personality_service()
        profile = personality.get_profile()
        
        return jsonify({
            'casual': round(profile.tone_markers.get('casual', 0.5) * 100),
            'formal': round(profile.tone_markers.get('formal', 0.5) * 100),
            'enthusiastic': round(profile.tone_markers.get('enthusiastic', 0.5) * 100),
            'sarcastic': round(profile.tone_markers.get('sarcastic', 0) * 100),
            'brief': round(profile.tone_markers.get('brief', 0.5) * 100),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@visualization_bp.route('/predictions', methods=['GET'])
def get_predictions():
    """Get personality-based predictions about the user."""
    try:
        personality = get_personality_service()
        profile = personality.get_profile()
        
        predictions = []
        
        # Communication style predictions
        if profile.tone_markers.get('casual', 0.5) > 0.7:
            predictions.append({
                'category': 'Communication',
                'prediction': 'You prefer informal, friendly conversations',
                'confidence': round(profile.tone_markers['casual'] * 100)
            })
        elif profile.tone_markers.get('formal', 0.5) > 0.6:
            predictions.append({
                'category': 'Communication',
                'prediction': 'You tend to be more professional in your writing',
                'confidence': round(profile.tone_markers['formal'] * 100)
            })
        
        # Message style
        if profile.tone_markers.get('brief', 0.5) > 0.7:
            predictions.append({
                'category': 'Style',
                'prediction': 'You get straight to the point with short messages',
                'confidence': round(profile.tone_markers['brief'] * 100)
            })
        elif profile.avg_message_length > 80:
            predictions.append({
                'category': 'Style',
                'prediction': 'You like to give detailed, thorough responses',
                'confidence': 75
            })
        
        # Emoji usage
        if profile.emoji_patterns:
            top_emoji = max(profile.emoji_patterns.items(), key=lambda x: x[1])[0]
            predictions.append({
                'category': 'Expression',
                'prediction': f'Your favorite emoji is {top_emoji}',
                'confidence': 90
            })
        
        # Enthusiasm
        if profile.tone_markers.get('enthusiastic', 0.5) > 0.6:
            predictions.append({
                'category': 'Personality',
                'prediction': 'You bring energy and positivity to conversations',
                'confidence': round(profile.tone_markers['enthusiastic'] * 100)
            })
        
        # Facts-based predictions
        for fact in profile.facts[:3]:
            if 'love' in fact.lower() or 'like' in fact.lower():
                predictions.append({
                    'category': 'Interests',
                    'prediction': f'You {fact}',
                    'confidence': 95
                })
        
        # Quirks
        if 'lol' in profile.typing_quirks or 'haha' in profile.typing_quirks:
            predictions.append({
                'category': 'Humor',
                'prediction': 'You frequently use laughter expressions',
                'confidence': 85
            })
        
        return jsonify({
            'predictions': predictions,
            'total_data_points': len(profile.vocabulary) + len(profile.facts) + len(profile.response_examples)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

"""
Timeline Routes - API endpoints for semantic memory timeline.
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from services.memory_service import get_memory_service
from services.personality_service import get_personality_service

timeline_bp = Blueprint('timeline', __name__, url_prefix='/api/timeline')


@timeline_bp.route('/memories', methods=['GET'])
def get_memories():
    """Get memories grouped by date for the timeline."""
    memory = get_memory_service()
    personality = get_personality_service()
    
    # Get time range from query params
    days = request.args.get('days', 30, type=int)
    
    try:
        # Get all training examples with metadata
        all_memories = memory.get_all_examples_with_metadata()
        
        # Group by date
        memories_by_date = {}
        for mem in all_memories:
            # Extract date from timestamp or use today
            timestamp = mem.get('timestamp', datetime.now().isoformat())
            if isinstance(timestamp, str):
                try:
                    date_obj = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    date_obj = datetime.now()
            else:
                date_obj = timestamp
            
            date_key = date_obj.strftime('%Y-%m-%d')
            
            if date_key not in memories_by_date:
                memories_by_date[date_key] = {
                    'date': date_key,
                    'memories': [],
                    'count': 0
                }
            
            memories_by_date[date_key]['memories'].append({
                'type': mem.get('type', 'training'),
                'content': mem.get('content', ''),
                'source': mem.get('source', 'unknown'),
                'timestamp': timestamp
            })
            memories_by_date[date_key]['count'] += 1
        
        # Also add facts from personality
        profile = personality.get_profile()
        today = datetime.now().strftime('%Y-%m-%d')
        
        if today not in memories_by_date:
            memories_by_date[today] = {'date': today, 'memories': [], 'count': 0}
        
        for fact in profile.facts:
            memories_by_date[today]['memories'].append({
                'type': 'fact',
                'content': fact,
                'source': 'manual',
                'timestamp': datetime.now().isoformat()
            })
            memories_by_date[today]['count'] += 1
        
        # Convert to list and sort by date
        timeline = sorted(memories_by_date.values(), key=lambda x: x['date'], reverse=True)
        
        return jsonify({
            'timeline': timeline[:days],
            'total_days': len(timeline),
            'total_memories': sum(d['count'] for d in timeline)
        })
        
    except Exception as e:
        print(f"Timeline error: {e}")
        return jsonify({'error': str(e)}), 500


@timeline_bp.route('/insights', methods=['GET'])
def get_insights():
    """Get learning insights and milestones."""
    memory = get_memory_service()
    personality = get_personality_service()
    
    try:
        stats = memory.get_training_stats()
        profile = personality.get_profile()
        
        insights = []
        
        # Training progress insight
        total = stats.get('total_examples', 0)
        if total > 0:
            if total < 50:
                insights.append({
                    'type': 'progress',
                    'icon': '🌱',
                    'title': 'Just Getting Started',
                    'description': f'Your clone has {total} examples. Add more for better responses!'
                })
            elif total < 200:
                insights.append({
                    'type': 'progress',
                    'icon': '🌿',
                    'title': 'Growing',
                    'description': f'With {total} examples, your clone is learning your style.'
                })
            else:
                insights.append({
                    'type': 'progress',
                    'icon': '🌳',
                    'title': 'Well Trained',
                    'description': f'Your clone has {total} examples and knows you well!'
                })
        
        # Source diversity
        sources = stats.get('sources', {})
        if len(sources) > 1:
            insights.append({
                'type': 'diversity',
                'icon': '🌈',
                'title': 'Diverse Training',
                'description': f'Trained from {len(sources)} different sources: {", ".join(sources.keys())}'
            })
        
        # Personality insight
        if profile.tone_markers:
            dominant_trait = max(profile.tone_markers.items(), key=lambda x: x[1])
            insights.append({
                'type': 'personality',
                'icon': '🎭',
                'title': f'Dominant Trait: {dominant_trait[0].title()}',
                'description': f'Your communication style is {round(dominant_trait[1] * 100)}% {dominant_trait[0]}'
            })
        
        # Facts insight
        if len(profile.facts) > 0:
            insights.append({
                'type': 'facts',
                'icon': '📝',
                'title': f'{len(profile.facts)} Facts About You',
                'description': 'Your clone knows personal details to make responses authentic.'
            })
        
        return jsonify({'insights': insights})
        
    except Exception as e:
        print(f"Insights error: {e}")
        return jsonify({'error': str(e)}), 500


@timeline_bp.route('/day/<date>', methods=['GET'])
def get_day_details(date: str):
    """Get detailed memories for a specific day."""
    memory = get_memory_service()
    
    try:
        all_memories = memory.get_all_examples_with_metadata()
        
        day_memories = []
        for mem in all_memories:
            timestamp = mem.get('timestamp', '')
            if timestamp.startswith(date):
                day_memories.append({
                    'type': mem.get('type', 'training'),
                    'content': mem.get('content', ''),
                    'context': mem.get('context', ''),
                    'source': mem.get('source', 'unknown'),
                    'timestamp': timestamp
                })
        
        return jsonify({
            'date': date,
            'memories': day_memories,
            'count': len(day_memories)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

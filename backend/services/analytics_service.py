"""
Analytics Service - Track and analyze conversation patterns.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import Counter
import json
import os
from config import Config


class AnalyticsService:
    """Service for tracking conversation analytics."""
    
    def __init__(self):
        self.analytics_file = os.path.join(Config.DATA_DIR, 'analytics.json')
        self.data = self._load_data()
    
    def _load_data(self) -> Dict:
        """Load analytics data from file."""
        if os.path.exists(self.analytics_file):
            try:
                with open(self.analytics_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            'conversations': [],
            'daily_stats': {},
            'topics': {},
            'response_times': [],
            'quality_scores': []
        }
    
    def _save_data(self):
        """Save analytics data to file."""
        os.makedirs(os.path.dirname(self.analytics_file), exist_ok=True)
        with open(self.analytics_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, default=str)
    
    def log_conversation(
        self,
        user_message: str,
        bot_response: str,
        response_time_ms: int,
        confidence: float = 0.0,
        is_training: bool = False
    ):
        """Log a conversation exchange."""
        now = datetime.now()
        date_key = now.strftime('%Y-%m-%d')
        hour = now.hour
        
        # Add to conversations list
        self.data['conversations'].append({
            'timestamp': now.isoformat(),
            'user_message': user_message[:200],
            'bot_response': bot_response[:200],
            'response_time_ms': response_time_ms,
            'confidence': confidence,
            'is_training': is_training
        })
        
        # Keep only last 1000 conversations
        if len(self.data['conversations']) > 1000:
            self.data['conversations'] = self.data['conversations'][-1000:]
        
        # Update daily stats
        if date_key not in self.data['daily_stats']:
            self.data['daily_stats'][date_key] = {
                'total_messages': 0,
                'training_messages': 0,
                'hours': {}
            }
        
        self.data['daily_stats'][date_key]['total_messages'] += 1
        if is_training:
            self.data['daily_stats'][date_key]['training_messages'] += 1
        
        # Track hourly activity
        hour_key = str(hour)
        if hour_key not in self.data['daily_stats'][date_key]['hours']:
            self.data['daily_stats'][date_key]['hours'][hour_key] = 0
        self.data['daily_stats'][date_key]['hours'][hour_key] += 1
        
        # Track response times
        self.data['response_times'].append(response_time_ms)
        if len(self.data['response_times']) > 500:
            self.data['response_times'] = self.data['response_times'][-500:]
        
        # Track quality scores
        if confidence > 0:
            self.data['quality_scores'].append(confidence)
            if len(self.data['quality_scores']) > 500:
                self.data['quality_scores'] = self.data['quality_scores'][-500:]
        
        # Extract and track topics (simple keyword extraction)
        self._extract_topics(user_message)
        
        self._save_data()
    
    def _extract_topics(self, message: str):
        """Extract topics from message."""
        # Simple keyword extraction
        words = message.lower().split()
        # Filter short words and common words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                      'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                      'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which',
                      'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'to',
                      'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'or',
                      'and', 'but', 'if', 'so', 'as', 'just', 'like', 'your', 'my'}
        
        keywords = [w for w in words if len(w) > 3 and w not in stop_words and w.isalpha()]
        
        for keyword in keywords[:5]:  # Max 5 keywords per message
            if keyword not in self.data['topics']:
                self.data['topics'][keyword] = 0
            self.data['topics'][keyword] += 1
    
    def get_dashboard_data(self) -> Dict:
        """Get analytics data for dashboard."""
        # Calculate stats
        total_conversations = len(self.data['conversations'])
        
        # Average response time
        avg_response_time = 0
        if self.data['response_times']:
            avg_response_time = sum(self.data['response_times']) / len(self.data['response_times'])
        
        # Average confidence
        avg_confidence = 0
        if self.data['quality_scores']:
            avg_confidence = sum(self.data['quality_scores']) / len(self.data['quality_scores'])
        
        # Top topics
        top_topics = sorted(self.data['topics'].items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Activity by hour (last 7 days)
        hourly_activity = [0] * 24
        last_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        for date_key, stats in self.data['daily_stats'].items():
            if date_key >= last_week:
                for hour, count in stats.get('hours', {}).items():
                    hourly_activity[int(hour)] += count
        
        # Recent daily activity
        daily_activity = []
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            stats = self.data['daily_stats'].get(date, {'total_messages': 0, 'training_messages': 0})
            daily_activity.append({
                'date': date,
                'total': stats['total_messages'],
                'training': stats.get('training_messages', 0)
            })
        
        return {
            'total_conversations': total_conversations,
            'avg_response_time_ms': round(avg_response_time),
            'avg_confidence': round(avg_confidence * 100),
            'top_topics': [{'topic': t[0], 'count': t[1]} for t in top_topics],
            'hourly_activity': hourly_activity,
            'daily_activity': list(reversed(daily_activity)),
            'peak_hour': hourly_activity.index(max(hourly_activity)) if max(hourly_activity) > 0 else 12
        }
    
    def get_suggestions(self) -> List[Dict]:
        """Get training suggestions based on analytics."""
        suggestions = []
        
        # Suggest based on low confidence topics
        if len(self.data['quality_scores']) > 10:
            avg = sum(self.data['quality_scores']) / len(self.data['quality_scores'])
            if avg < 0.7:
                suggestions.append({
                    'type': 'training',
                    'icon': '📚',
                    'title': 'More Training Needed',
                    'description': f'Average confidence is {round(avg*100)}%. Add more training examples!'
                })
        
        # Suggest based on conversation volume
        total = len(self.data['conversations'])
        if total < 50:
            suggestions.append({
                'type': 'usage',
                'icon': '💬',
                'title': 'Keep Chatting',
                'description': 'Have more conversations to help your clone learn patterns.'
            })
        
        # Suggest based on response time
        if self.data['response_times']:
            avg_time = sum(self.data['response_times']) / len(self.data['response_times'])
            if avg_time > 3000:
                suggestions.append({
                    'type': 'performance',
                    'icon': '⚡',
                    'title': 'Slow Responses',
                    'description': 'Consider using a faster model or local inference.'
                })
        
        return suggestions


# Singleton instance
_analytics_service = None

def get_analytics_service() -> AnalyticsService:
    """Get the singleton analytics service instance."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service

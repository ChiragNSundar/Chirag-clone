"""
Conversation Analytics Service - Deep analytics on conversations and interactions.
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import re

from .logger import get_logger

logger = get_logger(__name__)


class ConversationAnalyticsService:
    """Service for analyzing conversation patterns and metrics."""
    
    def __init__(self):
        self._conversations: List[Dict] = []
        self._max_stored = 1000
        self._topic_cache: Dict[str, int] = defaultdict(int)
    
    def log_conversation(
        self,
        user_message: str,
        bot_response: str,
        session_id: str = "default",
        response_time_ms: int = 0,
        emotion: Optional[str] = None
    ):
        """Log a conversation for analytics."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id,
            'user_message': user_message,
            'bot_response': bot_response,
            'user_words': len(user_message.split()),
            'bot_words': len(bot_response.split()),
            'response_time_ms': response_time_ms,
            'emotion': emotion,
            'hour': datetime.now().hour,
            'day_of_week': datetime.now().weekday()
        }
        
        self._conversations.append(entry)
        
        # Extract topics
        self._extract_topics(user_message)
        
        # Trim if needed
        if len(self._conversations) > self._max_stored:
            self._conversations = self._conversations[-self._max_stored:]
    
    def _extract_topics(self, text: str):
        """Extract topics/keywords from text."""
        # Simple keyword extraction
        words = re.findall(r'\b[a-z]{4,}\b', text.lower())
        
        # Filter common words
        stopwords = {'that', 'this', 'what', 'where', 'when', 'which', 'with', 
                     'have', 'been', 'were', 'they', 'their', 'about', 'would',
                     'could', 'should', 'there', 'these', 'those', 'from', 'into'}
        
        for word in words:
            if word not in stopwords:
                self._topic_cache[word] += 1
    
    def get_conversation_stats(self) -> Dict:
        """Get overall conversation statistics."""
        if not self._conversations:
            return {
                'total_conversations': 0,
                'avg_user_words': 0,
                'avg_bot_words': 0,
                'avg_response_time_ms': 0
            }
        
        total = len(self._conversations)
        
        return {
            'total_conversations': total,
            'avg_user_words': round(sum(c['user_words'] for c in self._conversations) / total, 1),
            'avg_bot_words': round(sum(c['bot_words'] for c in self._conversations) / total, 1),
            'avg_response_time_ms': round(sum(c['response_time_ms'] for c in self._conversations) / total, 1),
            'sessions': len(set(c['session_id'] for c in self._conversations))
        }
    
    def get_topic_distribution(self, limit: int = 20) -> List[Dict]:
        """Get top topics from conversations."""
        top_topics = sorted(
            self._topic_cache.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        return [{'topic': t, 'count': c} for t, c in top_topics]
    
    def get_activity_heatmap(self) -> Dict[str, List[int]]:
        """Get activity by hour and day of week."""
        heatmap = {
            'hours': [0] * 24,
            'days': [0] * 7
        }
        
        for conv in self._conversations:
            hour = conv.get('hour', 0)
            day = conv.get('day_of_week', 0)
            heatmap['hours'][hour] += 1
            heatmap['days'][day] += 1
        
        return heatmap
    
    def get_emotion_distribution(self) -> Dict[str, int]:
        """Get distribution of detected emotions."""
        emotions = [c.get('emotion') for c in self._conversations if c.get('emotion')]
        return dict(Counter(emotions))
    
    def get_response_time_trend(self, limit: int = 50) -> List[Dict]:
        """Get response time trend over recent conversations."""
        recent = self._conversations[-limit:]
        return [
            {
                'timestamp': c['timestamp'],
                'response_time_ms': c['response_time_ms']
            }
            for c in recent
        ]
    
    def get_daily_activity(self, days: int = 7) -> List[Dict]:
        """Get conversation count by day."""
        now = datetime.now()
        daily = defaultdict(int)
        
        for conv in self._conversations:
            try:
                ts = datetime.fromisoformat(conv['timestamp'])
                if (now - ts).days < days:
                    date_str = ts.strftime('%Y-%m-%d')
                    daily[date_str] += 1
            except:
                pass
        
        return [{'date': d, 'count': c} for d, c in sorted(daily.items())]
    
    def get_session_summary(self, session_id: str) -> Dict:
        """Get summary for a specific session."""
        session_convs = [c for c in self._conversations if c['session_id'] == session_id]
        
        if not session_convs:
            return {'error': 'Session not found'}
        
        return {
            'session_id': session_id,
            'message_count': len(session_convs),
            'total_user_words': sum(c['user_words'] for c in session_convs),
            'total_bot_words': sum(c['bot_words'] for c in session_convs),
            'avg_response_time': round(sum(c['response_time_ms'] for c in session_convs) / len(session_convs), 1),
            'first_message': session_convs[0]['timestamp'] if session_convs else None,
            'last_message': session_convs[-1]['timestamp'] if session_convs else None
        }
    
    def get_comprehensive_analytics(self) -> Dict:
        """Get all analytics in one call."""
        return {
            'stats': self.get_conversation_stats(),
            'topics': self.get_topic_distribution(15),
            'activity': self.get_activity_heatmap(),
            'emotions': self.get_emotion_distribution(),
            'response_trend': self.get_response_time_trend(30),
            'daily': self.get_daily_activity(7)
        }


# Singleton instance
_conversation_analytics_service: Optional[ConversationAnalyticsService] = None


def get_conversation_analytics_service() -> ConversationAnalyticsService:
    """Get the singleton conversation analytics service instance."""
    global _conversation_analytics_service
    if _conversation_analytics_service is None:
        _conversation_analytics_service = ConversationAnalyticsService()
    return _conversation_analytics_service

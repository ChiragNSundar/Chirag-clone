"""
Personality History Service - Track personality evolution over time.
Stores snapshots and enables comparison.
"""
from typing import Dict, Optional, List
from datetime import datetime
import json
import os

from .personality_service import get_personality_service
from .logger import get_logger
from config import Config

logger = get_logger(__name__)


class PersonalityHistoryService:
    """Service for tracking personality changes over time."""
    
    def __init__(self):
        self.personality = get_personality_service()
        self._history_file = os.path.join(Config.DATA_DIR, 'personality_history.json')
        self._snapshots: List[Dict] = []
        self._load_history()
    
    def _load_history(self):
        """Load history from file."""
        try:
            if os.path.exists(self._history_file):
                with open(self._history_file, 'r') as f:
                    self._snapshots = json.load(f)
        except Exception as e:
            logger.error(f"Error loading personality history: {e}")
            self._snapshots = []
    
    def _save_history(self):
        """Save history to file."""
        try:
            os.makedirs(os.path.dirname(self._history_file), exist_ok=True)
            with open(self._history_file, 'w') as f:
                json.dump(self._snapshots, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving personality history: {e}")
    
    def take_snapshot(self, note: str = "") -> Dict:
        """Take a snapshot of current personality."""
        profile = self.personality.get_profile()
        
        snapshot = {
            'id': f"snapshot_{datetime.now().timestamp()}",
            'timestamp': datetime.now().isoformat(),
            'note': note,
            'profile': {
                'name': profile.name,
                'summary': profile.summary,
                'facts_count': len(profile.facts),
                'quirks_count': len(profile.quirks),
                'emoji_count': len(profile.emojis),
                'common_phrases': profile.common_phrases[:10],
                'tone_markers': dict(list(profile.tone_markers.items())[:10]),
                'avg_message_length': profile.avg_message_length,
                'training_examples': profile.training_examples
            }
        }
        
        self._snapshots.append(snapshot)
        self._save_history()
        
        return snapshot
    
    def get_snapshots(self, limit: int = 20) -> List[Dict]:
        """Get recent snapshots."""
        return self._snapshots[-limit:]
    
    def get_snapshot(self, snapshot_id: str) -> Optional[Dict]:
        """Get a specific snapshot by ID."""
        for snapshot in self._snapshots:
            if snapshot.get('id') == snapshot_id:
                return snapshot
        return None
    
    def compare_snapshots(self, id1: str, id2: str) -> Dict:
        """Compare two snapshots."""
        snap1 = self.get_snapshot(id1)
        snap2 = self.get_snapshot(id2)
        
        if not snap1 or not snap2:
            return {'error': 'Snapshot(s) not found'}
        
        p1 = snap1['profile']
        p2 = snap2['profile']
        
        return {
            'snapshot1': {'id': id1, 'timestamp': snap1['timestamp']},
            'snapshot2': {'id': id2, 'timestamp': snap2['timestamp']},
            'changes': {
                'facts_count': p2['facts_count'] - p1['facts_count'],
                'quirks_count': p2['quirks_count'] - p1['quirks_count'],
                'emoji_count': p2['emoji_count'] - p1['emoji_count'],
                'training_examples': p2['training_examples'] - p1['training_examples'],
                'avg_message_length_change': round(p2['avg_message_length'] - p1['avg_message_length'], 1),
                'new_phrases': [p for p in p2['common_phrases'] if p not in p1['common_phrases']],
                'lost_phrases': [p for p in p1['common_phrases'] if p not in p2['common_phrases']]
            }
        }
    
    def get_evolution_trend(self) -> Dict:
        """Get trend data for personality evolution over time."""
        if len(self._snapshots) < 2:
            return {'error': 'Need at least 2 snapshots for trend'}
        
        trend = {
            'timestamps': [],
            'facts': [],
            'quirks': [],
            'training_examples': [],
            'avg_message_length': []
        }
        
        for snap in self._snapshots:
            p = snap['profile']
            trend['timestamps'].append(snap['timestamp'])
            trend['facts'].append(p['facts_count'])
            trend['quirks'].append(p['quirks_count'])
            trend['training_examples'].append(p['training_examples'])
            trend['avg_message_length'].append(p['avg_message_length'])
        
        return trend
    
    def get_growth_rate(self) -> Dict:
        """Calculate growth rate of personality data."""
        if len(self._snapshots) < 2:
            return {}
        
        first = self._snapshots[0]['profile']
        last = self._snapshots[-1]['profile']
        
        days_elapsed = 1  # Minimum
        try:
            first_date = datetime.fromisoformat(self._snapshots[0]['timestamp'])
            last_date = datetime.fromisoformat(self._snapshots[-1]['timestamp'])
            days_elapsed = max((last_date - first_date).days, 1)
        except:
            pass
        
        return {
            'days_tracked': days_elapsed,
            'snapshots_count': len(self._snapshots),
            'facts_per_day': round((last['facts_count'] - first['facts_count']) / days_elapsed, 2),
            'training_per_day': round((last['training_examples'] - first['training_examples']) / days_elapsed, 2),
            'total_growth': {
                'facts': last['facts_count'] - first['facts_count'],
                'quirks': last['quirks_count'] - first['quirks_count'],
                'training_examples': last['training_examples'] - first['training_examples']
            }
        }
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        initial_len = len(self._snapshots)
        self._snapshots = [s for s in self._snapshots if s.get('id') != snapshot_id]
        
        if len(self._snapshots) < initial_len:
            self._save_history()
            return True
        return False


# Singleton instance
_personality_history_service: Optional[PersonalityHistoryService] = None


def get_personality_history_service() -> PersonalityHistoryService:
    """Get the singleton personality history service instance."""
    global _personality_history_service
    if _personality_history_service is None:
        _personality_history_service = PersonalityHistoryService()
    return _personality_history_service

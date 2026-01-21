"""
Daily Briefing Service - Generates morning audio summaries.
Combines calendar events, pending drafts, and knowledge stats into a personalized briefing.
"""
import os
from datetime import datetime
from typing import Dict, Optional

from .logger import get_logger
from .personality_service import get_personality_service

logger = get_logger(__name__)


class DailyBriefingService:
    """Service for generating daily audio briefings."""
    
    def __init__(self):
        self.personality = get_personality_service()
        self._cached_briefing = None
        self._cache_date = None
    
    def generate_briefing_text(self) -> Dict:
        """Generate the text content for today's briefing."""
        profile = self.personality.get_profile()
        sections = []
        
        # 1. Greeting
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"
        
        sections.append(f"{greeting}! Here's your daily briefing.")
        
        # 2. Calendar section
        try:
            from .calendar_service import get_calendar_service
            calendar = get_calendar_service()
            
            if calendar.service:
                events = calendar.get_upcoming_events(days=1, max_results=5)
                if events:
                    sections.append(f"\n📅 You have {len(events)} event{'s' if len(events) != 1 else ''} today:")
                    for event in events:
                        start_time = event.get('start', '')
                        if 'T' in start_time:
                            time_str = start_time.split('T')[1][:5]
                        else:
                            time_str = 'All day'
                        sections.append(f"  • {event['summary']} at {time_str}")
                else:
                    sections.append("\n📅 Your calendar is clear today. Great time for deep work!")
            else:
                sections.append("\n📅 Calendar not connected.")
        except Exception as e:
            logger.warning(f"Calendar briefing failed: {e}")
            sections.append("\n📅 Could not load calendar.")
        
        # 3. Pending drafts section
        try:
            from .discord_bot_service import get_discord_service
            from .telegram_bot_service import get_telegram_service
            
            discord = get_discord_service()
            telegram = get_telegram_service()
            
            discord_drafts = len(discord.pending_replies) if hasattr(discord, 'pending_replies') else 0
            telegram_drafts = len(telegram.pending_replies) if hasattr(telegram, 'pending_replies') else 0
            
            total_drafts = discord_drafts + telegram_drafts
            if total_drafts > 0:
                sections.append(f"\n✉️ You have {total_drafts} pending draft message{'s' if total_drafts != 1 else ''} to review.")
        except Exception:
            pass
        
        # 4. Knowledge base stats
        try:
            from .knowledge_service import get_knowledge_service
            knowledge = get_knowledge_service()
            stats = knowledge.get_stats()
            
            if stats.get('total_documents', 0) > 0:
                sections.append(f"\n🧠 Your brain contains {stats['total_documents']} documents with {stats['total_chunks']} knowledge chunks.")
        except Exception:
            pass
        
        # 5. Closing
        sections.append("\n\nThat's your briefing. Have a productive day!")
        
        full_text = '\n'.join(sections)
        
        return {
            'text': full_text,
            'generated_at': datetime.now().isoformat(),
            'sections': {
                'calendar': True,
                'drafts': True,
                'knowledge': True
            }
        }
    
    def generate_audio_briefing(self) -> Optional[str]:
        """Generate audio file for the daily briefing using TTS."""
        # Check cache - only regenerate once per day
        today = datetime.now().date()
        if self._cache_date == today and self._cached_briefing:
            return self._cached_briefing
        
        try:
            from .voice_service import get_voice_service
            voice = get_voice_service()
            
            if not voice.tts_available:
                logger.warning("TTS not available for daily briefing")
                return None
            
            briefing = self.generate_briefing_text()
            
            # Generate audio
            from config import Config
            audio_path = os.path.join(Config.DATA_DIR, 'audio_cache', f'briefing_{today.isoformat()}.mp3')
            os.makedirs(os.path.dirname(audio_path), exist_ok=True)
            
            audio_data = voice.text_to_speech(briefing['text'])
            
            if audio_data:
                with open(audio_path, 'wb') as f:
                    f.write(audio_data)
                
                self._cached_briefing = audio_path
                self._cache_date = today
                
                logger.info(f"Generated daily briefing audio: {audio_path}")
                return audio_path
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate audio briefing: {e}")
            return None
    
    def get_briefing(self, audio: bool = False) -> Dict:
        """Get today's briefing, optionally with audio."""
        text_briefing = self.generate_briefing_text()
        
        result = {
            'text': text_briefing['text'],
            'generated_at': text_briefing['generated_at'],
            'audio_url': None
        }
        
        if audio:
            audio_path = self.generate_audio_briefing()
            if audio_path and os.path.exists(audio_path):
                # Return relative URL for API
                result['audio_url'] = f"/api/briefing/audio/{os.path.basename(audio_path)}"
        
        return result


# Singleton instance
_briefing_service: Optional[DailyBriefingService] = None


def get_briefing_service() -> DailyBriefingService:
    """Get the singleton briefing service instance."""
    global _briefing_service
    if _briefing_service is None:
        _briefing_service = DailyBriefingService()
    return _briefing_service

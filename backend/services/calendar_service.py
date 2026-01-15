"""
Calendar Service - Google Calendar integration for AI-assisted scheduling.
"""
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import os
import pickle

from .llm_service import get_llm_service
from .personality_service import get_personality_service
from .logger import get_logger
from config import Config

logger = get_logger(__name__)

# Try to import Google Calendar API
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    HAS_CALENDAR_API = True
except ImportError:
    HAS_CALENDAR_API = False
    logger.warning("Google Calendar API not installed.")

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly',
          'https://www.googleapis.com/auth/calendar.events']


class CalendarService:
    """Service for Google Calendar integration."""
    
    def __init__(self):
        self.llm = get_llm_service()
        self.personality = get_personality_service()
        
        self.client_id = os.getenv('GOOGLE_CALENDAR_CLIENT_ID', os.getenv('GMAIL_CLIENT_ID', ''))
        self.client_secret = os.getenv('GOOGLE_CALENDAR_CLIENT_SECRET', os.getenv('GMAIL_CLIENT_SECRET', ''))
        
        self.is_configured = bool(self.client_id and self.client_secret)
        self.service = None
        self.credentials_path = os.path.join(Config.DATA_DIR, 'calendar_token.pickle')
    
    def get_status(self) -> Dict:
        """Get service status."""
        return {
            'platform': 'google_calendar',
            'configured': self.is_configured,
            'connected': self.service is not None,
            'has_library': HAS_CALENDAR_API
        }
    
    def connect(self) -> bool:
        """Connect to Google Calendar API."""
        if not HAS_CALENDAR_API:
            return False
        
        creds = self._get_credentials()
        if not creds:
            return False
        
        try:
            self.service = build('calendar', 'v3', credentials=creds)
            return True
        except Exception as e:
            logger.error(f"Calendar connect error: {e}")
            return False
    
    def _get_credentials(self) -> Optional[Credentials]:
        """Load OAuth credentials."""
        creds = None
        
        if os.path.exists(self.credentials_path):
            try:
                with open(self.credentials_path, 'rb') as token:
                    creds = pickle.load(token)
            except Exception as e:
                logger.error(f"Error loading calendar credentials: {e}")
        
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except:
                creds = None
        
        return creds
    
    def get_upcoming_events(self, days: int = 7, max_results: int = 20) -> List[Dict]:
        """Get upcoming calendar events."""
        if not self.service:
            return []
        
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            end_time = (datetime.utcnow() + timedelta(days=days)).isoformat() + 'Z'
            
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=end_time,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            return [
                {
                    'id': e.get('id'),
                    'summary': e.get('summary', 'No Title'),
                    'start': e.get('start', {}).get('dateTime', e.get('start', {}).get('date')),
                    'end': e.get('end', {}).get('dateTime', e.get('end', {}).get('date')),
                    'location': e.get('location', ''),
                    'description': e.get('description', '')[:200] if e.get('description') else ''
                }
                for e in events
            ]
            
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return []
    
    def get_free_slots(self, date: str, duration_minutes: int = 60) -> List[Dict]:
        """Find free time slots on a given date."""
        if not self.service:
            return []
        
        try:
            # Parse date
            target_date = datetime.strptime(date, '%Y-%m-%d')
            start_of_day = target_date.replace(hour=9, minute=0)  # 9 AM
            end_of_day = target_date.replace(hour=18, minute=0)   # 6 PM
            
            # Get events for that day
            events = self.get_upcoming_events(days=1, max_results=50)
            
            # Filter events for target date
            day_events = []
            for e in events:
                try:
                    event_start = datetime.fromisoformat(e['start'].replace('Z', '+00:00'))
                    if event_start.date() == target_date.date():
                        day_events.append(e)
                except:
                    pass
            
            # Find gaps (simplified - would need proper busy time calculation)
            free_slots = []
            
            if not day_events:
                # Whole day is free
                free_slots.append({
                    'start': start_of_day.isoformat(),
                    'end': end_of_day.isoformat(),
                    'duration_minutes': (end_of_day - start_of_day).seconds // 60
                })
            
            return free_slots
            
        except Exception as e:
            logger.error(f"Error finding free slots: {e}")
            return []
    
    def suggest_meeting_time(self, description: str, attendees: List[str] = []) -> Dict:
        """Use AI to suggest best meeting time based on context."""
        profile = self.personality.get_profile()
        
        prompt = f"""You are {profile.name}'s calendar assistant. Based on the meeting description, suggest the best time.

Meeting: {description}
Attendees: {', '.join(attendees) if attendees else 'Just me'}

Consider:
- Morning for high-priority/creative work
- Afternoon for calls/meetings
- Avoid lunch hours

Suggest a time and day of week. Format: "DAY at TIME" (e.g., "Tuesday at 2:00 PM")

Suggestion:"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=50,
                temperature=0.7
            )
            
            return {
                'suggestion': response.strip(),
                'description': description,
                'reasoning': 'Based on typical scheduling patterns'
            }
            
        except Exception as e:
            logger.error(f"Meeting suggestion error: {e}")
            return {'error': str(e)}
    
    def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = ""
    ) -> Optional[Dict]:
        """Create a calendar event."""
        if not self.service:
            return None
        
        try:
            event = {
                'summary': summary,
                'location': location,
                'description': description,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'UTC'
                }
            }
            
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            return {
                'id': created_event.get('id'),
                'link': created_event.get('htmlLink')
            }
            
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            return None
    
    def get_today_summary(self) -> str:
        """Get an AI-generated summary of today's schedule."""
        events = self.get_upcoming_events(days=1, max_results=10)
        
        if not events:
            return "Your calendar is clear today! Perfect time for deep work or self-care."
        
        profile = self.personality.get_profile()
        
        events_text = "\n".join([
            f"- {e['summary']} at {e['start']}"
            for e in events
        ])
        
        prompt = f"""As {profile.name}'s assistant, summarize today's schedule in a friendly, conversational way:

Today's events:
{events_text}

Give a brief, helpful summary (2-3 sentences):"""

        try:
            return self.llm.generate(prompt=prompt, max_tokens=100, temperature=0.7).strip()
        except:
            return f"You have {len(events)} event(s) today."


# Singleton instance
_calendar_service: Optional[CalendarService] = None


def get_calendar_service() -> CalendarService:
    """Get the singleton calendar service instance."""
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = CalendarService()
    return _calendar_service

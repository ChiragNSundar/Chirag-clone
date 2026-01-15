"""
LinkedIn Bot Service - Draft DM response generation in user's professional style.
Note: Uses unofficial linkedin-api library as there's no official messaging API.
"""
from typing import List, Dict, Optional
from datetime import datetime
import os
import json

from .llm_service import get_llm_service
from .personality_service import get_personality_service
from .logger import get_logger

logger = get_logger(__name__)

# Try to import linkedin-api
try:
    from linkedin_api import Linkedin
    HAS_LINKEDIN = True
except ImportError:
    HAS_LINKEDIN = False
    logger.warning("linkedin-api not installed. LinkedIn integration disabled. Install with: pip install linkedin-api")


class LinkedInBotService:
    """Service for generating LinkedIn DM draft responses."""
    
    def __init__(self, chat_service=None):
        self.chat_service = chat_service
        self.llm = get_llm_service()
        self.personality = get_personality_service()
        
        # Credentials (email/password for unofficial API)
        self.email = os.getenv('LINKEDIN_EMAIL', '')
        self.password = os.getenv('LINKEDIN_PASSWORD', '')
        
        # State
        self.is_configured = bool(self.email and self.password)
        self.client = None
        self.draft_queue: List[Dict] = []
        
        # Note: We don't auto-init the LinkedIn client because it requires
        # actual login which should be user-initiated
    
    def connect(self) -> bool:
        """Connect to LinkedIn (requires user confirmation)."""
        if not HAS_LINKEDIN or not self.is_configured:
            return False
        
        try:
            self.client = Linkedin(self.email, self.password)
            logger.info("LinkedIn client connected")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to LinkedIn: {e}")
            self.client = None
            return False
    
    def disconnect(self):
        """Disconnect from LinkedIn."""
        self.client = None
    
    def get_status(self) -> Dict:
        """Get current service status."""
        return {
            'platform': 'linkedin',
            'configured': self.is_configured,
            'connected': self.client is not None,
            'has_library': HAS_LINKEDIN,
            'draft_count': len(self.draft_queue)
        }
    
    def fetch_conversations(self, limit: int = 10) -> List[Dict]:
        """Fetch recent conversations."""
        if not self.client:
            return []
        
        try:
            conversations = self.client.get_conversations()
            
            results = []
            for conv in conversations.get('elements', [])[:limit]:
                last_activity = conv.get('lastActivityAt', 0)
                
                results.append({
                    'id': conv.get('entityUrn', ''),
                    'last_activity': datetime.fromtimestamp(last_activity / 1000).isoformat() if last_activity else '',
                    'unread': conv.get('unreadCount', 0) > 0
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error fetching LinkedIn conversations: {e}")
            return []
    
    def generate_reply_draft(self, message_text: str, sender_name: str = "Someone") -> Dict:
        """Generate a professional draft reply in user's style."""
        profile = self.personality.get_profile()
        
        prompt = f"""You are {profile.name}'s LinkedIn clone. Generate a professional reply to this message.

Style notes:
- Keep it professional yet personable
- Match {profile.name}'s communication style
- Be helpful and engaging

Message from {sender_name}:
"{message_text}"

Generate a professional reply. Reply only with the message text, no quotes:"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=300,
                temperature=0.7
            )
            
            reply = response.strip().strip('"').strip("'")
            
            draft = {
                'id': f"li_draft_{datetime.now().timestamp()}",
                'type': 'reply',
                'sender_name': sender_name,
                'original_text': message_text,
                'draft_text': reply,
                'created_at': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            self.draft_queue.append(draft)
            return draft
            
        except Exception as e:
            logger.error(f"Error generating LinkedIn reply: {e}")
            return {'error': str(e)}
    
    def generate_connection_note(self, person_name: str, context: str = "") -> Dict:
        """Generate a connection request note."""
        profile = self.personality.get_profile()
        
        context_note = f" Context: {context}" if context else ""
        
        prompt = f"""You are {profile.name}'s LinkedIn clone. Generate a connection request note for {person_name}.{context_note}

Style notes:
- Professional and genuine
- Brief (under 300 characters)
- Give a reason for connecting

Generate the connection note only, no quotes:"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=100,
                temperature=0.7
            )
            
            note = response.strip().strip('"').strip("'")[:300]
            
            draft = {
                'id': f"li_draft_{datetime.now().timestamp()}",
                'type': 'connection_note',
                'person_name': person_name,
                'context': context,
                'draft_text': note,
                'created_at': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            self.draft_queue.append(draft)
            return draft
            
        except Exception as e:
            logger.error(f"Error generating connection note: {e}")
            return {'error': str(e)}
    
    def get_drafts(self, status: Optional[str] = None) -> List[Dict]:
        """Get all drafts."""
        if status:
            return [d for d in self.draft_queue if d.get('status') == status]
        return self.draft_queue
    
    def approve_draft(self, draft_id: str) -> Dict:
        """Approve a draft."""
        for draft in self.draft_queue:
            if draft.get('id') == draft_id:
                draft['status'] = 'approved'
                return draft
        return {'error': 'Draft not found'}
    
    def reject_draft(self, draft_id: str) -> Dict:
        """Reject a draft."""
        for draft in self.draft_queue:
            if draft.get('id') == draft_id:
                draft['status'] = 'rejected'
                return draft
        return {'error': 'Draft not found'}
    
    def clear_drafts(self, status: Optional[str] = None):
        """Clear drafts."""
        if status:
            self.draft_queue = [d for d in self.draft_queue if d.get('status') != status]
        else:
            self.draft_queue = []


# Singleton instance
_linkedin_bot_service: Optional[LinkedInBotService] = None


def get_linkedin_bot_service(chat_service=None) -> LinkedInBotService:
    """Get the singleton LinkedIn bot service instance."""
    global _linkedin_bot_service
    if _linkedin_bot_service is None:
        _linkedin_bot_service = LinkedInBotService(chat_service)
    return _linkedin_bot_service

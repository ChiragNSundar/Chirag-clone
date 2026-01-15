"""
WhatsApp Bot Service - WhatsApp Business API integration for auto-replies.
Note: Requires WhatsApp Business API access (paid service).
"""
from typing import Dict, Optional, List
from datetime import datetime
import os
import json

from .llm_service import get_llm_service
from .personality_service import get_personality_service
from .logger import get_logger

logger = get_logger(__name__)


class WhatsAppBotService:
    """Service for WhatsApp auto-reply drafts."""
    
    def __init__(self, chat_service=None):
        self.chat_service = chat_service
        self.llm = get_llm_service()
        self.personality = get_personality_service()
        
        # WhatsApp Business API credentials
        self.phone_number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
        self.access_token = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
        self.webhook_verify_token = os.getenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN', '')
        
        self.is_configured = bool(self.phone_number_id and self.access_token)
        self.draft_queue: List[Dict] = []
    
    def get_status(self) -> Dict:
        """Get service status."""
        return {
            'platform': 'whatsapp',
            'configured': self.is_configured,
            'draft_count': len(self.draft_queue)
        }
    
    def generate_reply_draft(
        self,
        message_text: str,
        sender_name: str = "Someone",
        sender_phone: str = ""
    ) -> Dict:
        """Generate a WhatsApp reply draft in user's style."""
        profile = self.personality.get_profile()
        
        prompt = f"""You are {profile.name}'s WhatsApp clone. Generate a reply to this message.

Style notes:
- Keep it casual and conversational (it's WhatsApp!)
- Use appropriate emojis: {', '.join(list(profile.emojis.keys())[:5])}
- Match {profile.name}'s texting style 
- Keep it brief (WhatsApp messages are usually short)

Message from {sender_name}:
"{message_text}"

Generate a natural WhatsApp reply. Reply text only:"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=150,
                temperature=0.8
            )
            
            reply = response.strip().strip('"').strip("'")
            
            draft = {
                'id': f"wa_draft_{datetime.now().timestamp()}",
                'type': 'reply',
                'sender_name': sender_name,
                'sender_phone': sender_phone,
                'original_text': message_text,
                'draft_text': reply,
                'created_at': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            self.draft_queue.append(draft)
            return draft
            
        except Exception as e:
            logger.error(f"WhatsApp reply error: {e}")
            return {'error': str(e)}
    
    def process_webhook(self, payload: Dict) -> Optional[Dict]:
        """Process incoming WhatsApp webhook."""
        try:
            # Parse WhatsApp webhook structure
            entry = payload.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            
            messages = value.get('messages', [])
            contacts = value.get('contacts', [])
            
            if not messages:
                return None
            
            message = messages[0]
            contact = contacts[0] if contacts else {}
            
            if message.get('type') != 'text':
                return None  # Only handle text messages for now
            
            message_text = message.get('text', {}).get('body', '')
            sender_name = contact.get('profile', {}).get('name', 'Unknown')
            sender_phone = message.get('from', '')
            
            # Generate draft reply
            return self.generate_reply_draft(
                message_text=message_text,
                sender_name=sender_name,
                sender_phone=sender_phone
            )
            
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return None
    
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
_whatsapp_bot_service: Optional[WhatsAppBotService] = None


def get_whatsapp_bot_service(chat_service=None) -> WhatsAppBotService:
    """Get the singleton WhatsApp bot service instance."""
    global _whatsapp_bot_service
    if _whatsapp_bot_service is None:
        _whatsapp_bot_service = WhatsAppBotService(chat_service)
    return _whatsapp_bot_service

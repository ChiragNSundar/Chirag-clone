"""
Gmail Bot Service - Draft email reply generation in user's style.
Uses Gmail API with OAuth 2.0.
"""
from typing import List, Dict, Optional
from datetime import datetime
import os
import json
import base64
from email.mime.text import MIMEText
import pickle

from .llm_service import get_llm_service
from .personality_service import get_personality_service
from .logger import get_logger
from config import Config

logger = get_logger(__name__)

# Try to import Google API libraries
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    HAS_GMAIL_API = True
except ImportError:
    HAS_GMAIL_API = False
    logger.warning("Google API libraries not installed. Gmail integration disabled. Install with: pip install google-api-python-client google-auth-oauthlib")

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose'
]


class GmailBotService:
    """Service for generating Gmail draft replies in user's style."""
    
    def __init__(self, chat_service=None):
        self.chat_service = chat_service
        self.llm = get_llm_service()
        self.personality = get_personality_service()
        
        # Credentials
        self.client_id = os.getenv('GMAIL_CLIENT_ID', '')
        self.client_secret = os.getenv('GMAIL_CLIENT_SECRET', '')
        
        # State
        self.is_configured = bool(self.client_id and self.client_secret)
        self.service = None
        self.draft_queue: List[Dict] = []
        self.credentials_path = os.path.join(Config.DATA_DIR, 'gmail_token.pickle')
    
    def _get_credentials(self) -> Optional[Credentials]:
        """Load or create OAuth credentials."""
        creds = None
        
        # Check for existing token
        if os.path.exists(self.credentials_path):
            try:
                with open(self.credentials_path, 'rb') as token:
                    creds = pickle.load(token)
            except Exception as e:
                logger.error(f"Error loading Gmail credentials: {e}")
        
        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Error refreshing credentials: {e}")
                creds = None
        
        return creds
    
    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        creds = self._get_credentials()
        return creds is not None and creds.valid
    
    def get_auth_url(self) -> Optional[str]:
        """Get OAuth URL for user authentication."""
        if not HAS_GMAIL_API or not self.is_configured:
            return None
        
        try:
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]
                    }
                },
                SCOPES
            )
            
            auth_url, _ = flow.authorization_url(prompt='consent')
            return auth_url
            
        except Exception as e:
            logger.error(f"Error getting auth URL: {e}")
            return None
    
    def connect(self) -> bool:
        """Connect to Gmail API with existing credentials."""
        if not HAS_GMAIL_API:
            return False
        
        creds = self._get_credentials()
        if not creds:
            return False
        
        try:
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Gmail service connected")
            return True
        except Exception as e:
            logger.error(f"Error connecting to Gmail: {e}")
            self.service = None
            return False
    
    def disconnect(self):
        """Disconnect from Gmail."""
        self.service = None
    
    def get_status(self) -> Dict:
        """Get current service status."""
        return {
            'platform': 'gmail',
            'configured': self.is_configured,
            'authenticated': self.is_authenticated(),
            'connected': self.service is not None,
            'has_library': HAS_GMAIL_API,
            'draft_count': len(self.draft_queue)
        }
    
    def fetch_unread_emails(self, max_results: int = 10) -> List[Dict]:
        """Fetch recent unread emails."""
        if not self.service:
            return []
        
        try:
            results = self.service.users().messages().list(
                userId='me',
                q='is:unread category:primary',
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for msg in messages:
                full_msg = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                headers = {h['name']: h['value'] for h in full_msg.get('payload', {}).get('headers', [])}
                
                emails.append({
                    'id': msg['id'],
                    'thread_id': full_msg.get('threadId', ''),
                    'from': headers.get('From', ''),
                    'subject': headers.get('Subject', ''),
                    'date': headers.get('Date', ''),
                    'snippet': full_msg.get('snippet', '')
                })
            
            return emails
            
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []
    
    def get_email_content(self, email_id: str) -> Optional[str]:
        """Get the full content of an email."""
        if not self.service:
            return None
        
        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()
            
            payload = msg.get('payload', {})
            
            # Try to get plain text body
            if payload.get('mimeType') == 'text/plain':
                data = payload.get('body', {}).get('data', '')
                return base64.urlsafe_b64decode(data).decode('utf-8')
            
            # Check parts
            for part in payload.get('parts', []):
                if part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            
            # Fallback to snippet
            return msg.get('snippet', '')
            
        except Exception as e:
            logger.error(f"Error getting email content: {e}")
            return None
    
    def generate_reply_draft(
        self,
        email_subject: str,
        email_body: str,
        sender_name: str = "Someone"
    ) -> Dict:
        """Generate a draft email reply in user's style."""
        profile = self.personality.get_profile()
        
        # Truncate body if too long
        body_preview = email_body[:1000] + "..." if len(email_body) > 1000 else email_body
        
        prompt = f"""You are {profile.name}'s email clone. Generate a reply to this email in their style.

Email from: {sender_name}
Subject: {email_subject}
Content:
{body_preview}

Style notes:
- Professional but personal
- Match {profile.name}'s typical email style
- Be helpful and concise

Generate the email reply body only (no subject/greeting needed if greeting is covered):"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=500,
                temperature=0.7
            )
            
            reply = response.strip()
            
            draft = {
                'id': f"gmail_draft_{datetime.now().timestamp()}",
                'type': 'reply',
                'sender_name': sender_name,
                'original_subject': email_subject,
                'original_body_preview': body_preview[:200],
                'draft_text': reply,
                'created_at': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            self.draft_queue.append(draft)
            return draft
            
        except Exception as e:
            logger.error(f"Error generating email reply: {e}")
            return {'error': str(e)}
    
    def create_gmail_draft(self, to: str, subject: str, body: str) -> Optional[Dict]:
        """Create an actual Gmail draft (not just local)."""
        if not self.service:
            return None
        
        try:
            message = MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            draft = self.service.users().drafts().create(
                userId='me',
                body={'message': {'raw': raw}}
            ).execute()
            
            return {
                'id': draft['id'],
                'message_id': draft.get('message', {}).get('id', '')
            }
            
        except Exception as e:
            logger.error(f"Error creating Gmail draft: {e}")
            return None
    
    def get_drafts(self, status: Optional[str] = None) -> List[Dict]:
        """Get all local drafts."""
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
        """Clear local drafts."""
        if status:
            self.draft_queue = [d for d in self.draft_queue if d.get('status') != status]
        else:
            self.draft_queue = []


# Singleton instance
_gmail_bot_service: Optional[GmailBotService] = None


def get_gmail_bot_service(chat_service=None) -> GmailBotService:
    """Get the singleton Gmail bot service instance."""
    global _gmail_bot_service
    if _gmail_bot_service is None:
        _gmail_bot_service = GmailBotService(chat_service)
    return _gmail_bot_service

"""
Slack Bot Service - Integration for Slack workspace automation.
"""
import os
from datetime import datetime
from typing import Dict, List, Optional

from .logger import get_logger
from .llm_service import get_llm_service
from .personality_service import get_personality_service

logger = get_logger(__name__)

# Try to import Slack SDK
try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    HAS_SLACK = True
except ImportError:
    HAS_SLACK = False
    logger.warning("slack-sdk not installed. Install with: pip install slack-sdk")


class SlackBotService:
    """Service for Slack workspace integration."""
    
    def __init__(self):
        self.bot_token = os.getenv('SLACK_BOT_TOKEN', '')
        self.is_configured = bool(self.bot_token)
        self.client = None
        self.is_running = False
        self.pending_replies: List[Dict] = []
        self.reply_log: List[Dict] = []
        
        if HAS_SLACK and self.is_configured:
            try:
                self.client = WebClient(token=self.bot_token)
                # Test connection
                auth_result = self.client.auth_test()
                self.bot_user_id = auth_result.get('user_id', '')
                self.bot_name = auth_result.get('user', 'SlackBot')
                logger.info(f"✅ Slack client initialized as @{self.bot_name}")
            except Exception as e:
                logger.error(f"Slack client init failed: {e}")
                self.client = None
    
    def get_status(self) -> Dict:
        """Get service status."""
        return {
            'platform': 'slack',
            'has_library': HAS_SLACK,
            'configured': self.is_configured,
            'connected': self.client is not None,
            'running': self.is_running,
            'pending_drafts': len(self.pending_replies),
            'bot_name': getattr(self, 'bot_name', None)
        }
    
    def get_recent_messages(self, channel_id: str, limit: int = 10) -> List[Dict]:
        """Get recent messages from a channel."""
        if not self.client:
            return []
        
        try:
            result = self.client.conversations_history(
                channel=channel_id,
                limit=limit
            )
            
            messages = []
            for msg in result.get('messages', []):
                if msg.get('type') == 'message' and not msg.get('subtype'):
                    messages.append({
                        'user': msg.get('user', ''),
                        'text': msg.get('text', ''),
                        'ts': msg.get('ts', ''),
                        'thread_ts': msg.get('thread_ts')
                    })
            
            return messages
            
        except SlackApiError as e:
            logger.error(f"Error fetching messages: {e}")
            return []
    
    def summarize_thread(self, channel_id: str, thread_ts: str) -> str:
        """Summarize a Slack thread using LLM."""
        if not self.client:
            return "Slack not connected."
        
        try:
            result = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts
            )
            
            messages = result.get('messages', [])
            if not messages:
                return "Empty thread."
            
            # Format thread for LLM
            thread_text = []
            for msg in messages:
                user = msg.get('user', 'Unknown')
                text = msg.get('text', '')
                thread_text.append(f"@{user}: {text}")
            
            llm = get_llm_service()
            personality = get_personality_service()
            profile = personality.get_profile()
            
            prompt = f"""Summarize this Slack thread in 2-3 sentences. Be concise but capture the key points and any action items:

{chr(10).join(thread_text)}

Summary:"""
            
            response = llm.generate_response(
                system_prompt=f"You are {profile.name}'s assistant. Summarize concisely.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.5
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Thread summarization failed: {e}")
            return f"Error: {e}"
    
    def generate_reply_draft(self, message_text: str, context: str = "") -> Dict:
        """Generate a reply draft in user's style."""
        try:
            llm = get_llm_service()
            personality = get_personality_service()
            profile = personality.get_profile()
            
            context_str = f"\nContext: {context}" if context else ""
            
            prompt = f"""Someone sent this message on Slack:{context_str}

"{message_text}"

Draft a professional reply in {profile.name}'s communication style.
Keep it concise (1-3 sentences) and workplace-appropriate.

Reply:"""
            
            response = llm.generate_response(
                system_prompt=f"You are {profile.name}. Reply as they would on Slack - professional but with personality.",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.7
            )
            
            draft = {
                'id': f"slack_{datetime.now().timestamp()}",
                'original_message': message_text,
                'draft_reply': response.strip(),
                'created_at': datetime.now().isoformat(),
                'platform': 'slack'
            }
            
            self.pending_replies.append(draft)
            return draft
            
        except Exception as e:
            logger.error(f"Draft generation failed: {e}")
            return {'error': str(e)}
    
    def send_message(self, channel_id: str, text: str, thread_ts: Optional[str] = None) -> bool:
        """Send a message to a Slack channel."""
        if not self.client:
            return False
        
        try:
            self.client.chat_postMessage(
                channel=channel_id,
                text=text,
                thread_ts=thread_ts
            )
            
            # Log the reply
            self.reply_log.append({
                'channel': channel_id,
                'message': text,
                'timestamp': datetime.now().isoformat(),
                'thread': thread_ts
            })
            
            return True
            
        except SlackApiError as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def get_dm_channels(self) -> List[Dict]:
        """Get list of DM channels."""
        if not self.client:
            return []
        
        try:
            result = self.client.conversations_list(
                types='im',
                limit=50
            )
            
            return [
                {'id': ch['id'], 'user': ch.get('user', '')}
                for ch in result.get('channels', [])
            ]
            
        except SlackApiError as e:
            logger.error(f"Error fetching DMs: {e}")
            return []


# Singleton instance
_slack_service: Optional[SlackBotService] = None


def get_slack_service() -> SlackBotService:
    """Get the singleton Slack service instance."""
    global _slack_service
    if _slack_service is None:
        _slack_service = SlackBotService()
    return _slack_service

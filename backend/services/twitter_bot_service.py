"""
Twitter/X Bot Service - Draft tweet/reply generation in user's style.
Uses Twitter API v2 OAuth 2.0 for authentication.
"""
from typing import List, Dict, Optional
from datetime import datetime
import os
import json

from .llm_service import get_llm_service
from .personality_service import get_personality_service
from .logger import get_logger

logger = get_logger(__name__)

# Try to import tweepy for Twitter API
try:
    import tweepy
    HAS_TWEEPY = True
except ImportError:
    HAS_TWEEPY = False
    logger.warning("Tweepy not installed. Twitter integration disabled. Install with: pip install tweepy")


class TwitterBotService:
    """Service for generating Twitter/X draft replies and tweets."""
    
    def __init__(self, chat_service=None):
        self.chat_service = chat_service
        self.llm = get_llm_service()
        self.personality = get_personality_service()
        
        # API credentials
        self.client_id = os.getenv('TWITTER_CLIENT_ID', '')
        self.client_secret = os.getenv('TWITTER_CLIENT_SECRET', '')
        self.access_token = os.getenv('TWITTER_ACCESS_TOKEN', '')
        self.access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET', '')
        
        # State
        self.is_configured = bool(self.access_token and self.access_token_secret)
        self.client = None
        self.draft_queue: List[Dict] = []
        self._init_client()
    
    def _init_client(self):
        """Initialize Twitter API client."""
        if not HAS_TWEEPY or not self.is_configured:
            return
        
        try:
            self.client = tweepy.Client(
                consumer_key=self.client_id,
                consumer_secret=self.client_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret
            )
            logger.info("Twitter client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {e}")
            self.client = None
    
    def get_status(self) -> Dict:
        """Get current service status."""
        return {
            'platform': 'twitter',
            'configured': self.is_configured,
            'connected': self.client is not None,
            'has_tweepy': HAS_TWEEPY,
            'draft_count': len(self.draft_queue)
        }
    
    def fetch_mentions(self, max_results: int = 10) -> List[Dict]:
        """Fetch recent mentions for drafting replies."""
        if not self.client:
            return []
        
        try:
            # Get authenticated user's ID
            me = self.client.get_me()
            if not me or not me.data:
                return []
            
            user_id = me.data.id
            
            # Fetch mentions
            mentions = self.client.get_users_mentions(
                id=user_id,
                max_results=max_results,
                tweet_fields=['created_at', 'author_id', 'text']
            )
            
            if not mentions or not mentions.data:
                return []
            
            return [
                {
                    'id': tweet.id,
                    'text': tweet.text,
                    'author_id': tweet.author_id,
                    'created_at': tweet.created_at.isoformat() if tweet.created_at else ''
                }
                for tweet in mentions.data
            ]
            
        except Exception as e:
            logger.error(f"Error fetching mentions: {e}")
            return []
    
    def generate_reply_draft(self, tweet_text: str, tweet_id: str = "") -> Dict:
        """Generate a draft reply in user's style."""
        profile = self.personality.get_profile()
        
        prompt = f"""You are {profile.name}'s Twitter clone. Generate a reply to this tweet in their exact style.

Style notes:
- Tone: {json.dumps(profile.tone_markers)}
- Common phrases: {', '.join(profile.common_phrases[:5])}
- Keep it Twitter-appropriate (concise, engaging)

Tweet to reply to:
"{tweet_text}"

Generate a reply (280 chars max). Reply only with the tweet text, no quotes or explanation:"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=100,
                temperature=0.8
            )
            
            # Clean and limit to 280 chars
            reply = response.strip().strip('"').strip("'")[:280]
            
            draft = {
                'id': f"draft_{datetime.now().timestamp()}",
                'type': 'reply',
                'original_tweet_id': tweet_id,
                'original_text': tweet_text,
                'draft_text': reply,
                'created_at': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            self.draft_queue.append(draft)
            return draft
            
        except Exception as e:
            logger.error(f"Error generating reply: {e}")
            return {'error': str(e)}
    
    def generate_tweet_draft(self, topic: str = "") -> Dict:
        """Generate a draft tweet in user's style."""
        profile = self.personality.get_profile()
        
        topic_prompt = f" about {topic}" if topic else ""
        
        prompt = f"""You are {profile.name}'s Twitter clone. Generate a tweet{topic_prompt} in their exact style.

Style notes:
- Tone: {json.dumps(profile.tone_markers)}
- Common phrases: {', '.join(profile.common_phrases[:5])}
- Make it engaging and authentic

Generate a tweet (280 chars max). Reply only with the tweet text:"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                max_tokens=100,
                temperature=0.9
            )
            
            tweet = response.strip().strip('"').strip("'")[:280]
            
            draft = {
                'id': f"draft_{datetime.now().timestamp()}",
                'type': 'tweet',
                'topic': topic,
                'draft_text': tweet,
                'created_at': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            self.draft_queue.append(draft)
            return draft
            
        except Exception as e:
            logger.error(f"Error generating tweet: {e}")
            return {'error': str(e)}
    
    def get_drafts(self, status: Optional[str] = None) -> List[Dict]:
        """Get all drafts, optionally filtered by status."""
        if status:
            return [d for d in self.draft_queue if d.get('status') == status]
        return self.draft_queue
    
    def approve_draft(self, draft_id: str) -> Dict:
        """Approve and post a draft (not auto-posting, just marks as approved)."""
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
        """Clear drafts, optionally only those with a specific status."""
        if status:
            self.draft_queue = [d for d in self.draft_queue if d.get('status') != status]
        else:
            self.draft_queue = []


# Singleton instance
_twitter_bot_service: Optional[TwitterBotService] = None


def get_twitter_bot_service(chat_service=None) -> TwitterBotService:
    """Get the singleton Twitter bot service instance."""
    global _twitter_bot_service
    if _twitter_bot_service is None:
        _twitter_bot_service = TwitterBotService(chat_service)
    return _twitter_bot_service

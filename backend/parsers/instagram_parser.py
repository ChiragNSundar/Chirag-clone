"""
Instagram Chat Parser - Parses exported Instagram DM data.
Handles the JSON format from Instagram's "Download Your Data" feature.
"""
import json
import re
from typing import List, Tuple, Dict, Optional
from datetime import datetime


class InstagramParser:
    """Parser for Instagram DM exports from the official data download."""
    
    def __init__(self, your_username: str):
        """
        Initialize the parser.
        
        Args:
            your_username: Your Instagram username
        """
        self.your_username = your_username.lower()
    
    def parse_file(self, file_path: str) -> Dict:
        """
        Parse an Instagram messages JSON file.
        
        The file structure from Instagram export:
        {
            "participants": [...],
            "messages": [
                {
                    "sender_name": "username",
                    "timestamp_ms": 1234567890000,
                    "content": "message text",
                    "type": "Generic"
                },
                ...
            ]
        }
        
        Args:
            file_path: Path to the messages JSON file
            
        Returns:
            Dict with messages, your_messages, and conversation_pairs
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return self.parse_data(data)
    
    def parse_data(self, data: Dict) -> Dict:
        """Parse Instagram messages data structure."""
        messages = []
        
        for msg in data.get('messages', []):
            content = msg.get('content', '')
            
            # Skip non-text messages
            if not content or self._should_skip(msg):
                continue
            
            # Decode Instagram's UTF-8 encoding issues
            try:
                content = content.encode('latin1').decode('utf-8')
            except:
                pass  # Keep original if encoding fails
            
            sender = msg.get('sender_name', 'Unknown')
            try:
                sender = sender.encode('latin1').decode('utf-8')
            except:
                pass
            
            is_you = self._is_your_message(sender)
            
            timestamp_ms = msg.get('timestamp_ms', 0)
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000).isoformat() if timestamp_ms else ''
            
            messages.append({
                'timestamp': timestamp,
                'timestamp_ms': timestamp_ms,
                'sender': sender,
                'content': content,
                'is_you': is_you,
                'type': msg.get('type', 'Generic')
            })
        
        # Instagram exports are in reverse chronological order, so reverse them
        messages.reverse()
        
        your_messages = [m for m in messages if m['is_you']]
        conversation_pairs = self._extract_conversation_pairs(messages)
        
        return {
            'total_messages': len(messages),
            'your_messages': len(your_messages),
            'messages': messages,
            'conversation_pairs': conversation_pairs,
            'your_texts': [m['content'] for m in your_messages],
            'participants': data.get('participants', [])
        }
    
    def parse_content(self, content: str) -> Dict:
        """
        Parse Instagram JSON content directly.
        
        Args:
            content: The raw JSON content
            
        Returns:
            Dict with parsed data
        """
        data = json.loads(content)
        return self.parse_data(data)
    
    def _is_your_message(self, sender: str) -> bool:
        """Check if a message was sent by you."""
        sender_lower = sender.lower().strip()
        
        if sender_lower == self.your_username:
            return True
        
        # Handle variations
        if self.your_username in sender_lower:
            return True
        
        return False
    
    def _should_skip(self, msg: Dict) -> bool:
        """Check if a message should be skipped."""
        msg_type = msg.get('type', '')
        
        # Skip non-text message types
        skip_types = ['Share', 'Call', 'MediaShare']
        if msg_type in skip_types:
            return True
        
        # Skip if it's a reaction
        if 'reactions' in msg and not msg.get('content'):
            return True
        
        # Skip media-only messages
        if msg.get('photos') or msg.get('videos') or msg.get('audio_files'):
            if not msg.get('content'):
                return True
        
        # Skip shared posts without text
        if msg.get('share') and not msg.get('content'):
            return True
        
        return False
    
    def _extract_conversation_pairs(self, messages: List[Dict]) -> List[Tuple[str, str]]:
        """
        Extract context-response pairs where you responded.
        
        Returns pairs of (context, your_response)
        """
        pairs = []
        
        for i, msg in enumerate(messages):
            if msg['is_you'] and i > 0:
                # Find previous non-you messages as context
                context_parts = []
                j = i - 1
                
                while j >= 0 and len(context_parts) < 3:
                    if not messages[j]['is_you']:
                        context_parts.insert(0, messages[j]['content'])
                    j -= 1
                
                if context_parts:
                    context = ' | '.join(context_parts)
                    pairs.append((context, msg['content']))
        
        return pairs
    
    def parse_inbox_folder(self, inbox_path: str) -> Dict:
        """
        Parse all conversation files in an Instagram inbox folder.
        
        The inbox structure from Instagram export:
        inbox/
            conversation_1/
                message_1.json
            conversation_2/
                message_1.json
        
        Args:
            inbox_path: Path to the inbox folder
            
        Returns:
            Combined dict with all messages
        """
        import os
        
        all_messages = []
        all_pairs = []
        all_your_texts = []
        
        for conv_folder in os.listdir(inbox_path):
            conv_path = os.path.join(inbox_path, conv_folder)
            
            if not os.path.isdir(conv_path):
                continue
            
            # Find message files
            for filename in os.listdir(conv_path):
                if filename.startswith('message') and filename.endswith('.json'):
                    file_path = os.path.join(conv_path, filename)
                    try:
                        result = self.parse_file(file_path)
                        all_messages.extend(result['messages'])
                        all_pairs.extend(result['conversation_pairs'])
                        all_your_texts.extend(result['your_texts'])
                    except Exception as e:
                        print(f"Error parsing {file_path}: {e}")
        
        your_messages = [m for m in all_messages if m['is_you']]
        
        return {
            'total_messages': len(all_messages),
            'your_messages': len(your_messages),
            'messages': all_messages,
            'conversation_pairs': all_pairs,
            'your_texts': all_your_texts
        }

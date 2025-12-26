"""
Discord Chat Parser - Parses exported Discord chat files.
Handles exports from DiscordChatExporter (JSON and CSV formats).
"""
import json
import csv
import re
from typing import List, Tuple, Dict, Optional
from datetime import datetime


class DiscordParser:
    """Parser for Discord chat exports from DiscordChatExporter."""
    
    def __init__(self, your_user_id: str = None, your_username: str = None):
        """
        Initialize the parser.
        
        Args:
            your_user_id: Your Discord user ID (preferred)
            your_username: Your Discord username (fallback)
        """
        self.your_user_id = your_user_id
        self.your_username = your_username.lower() if your_username else None
    
    def parse_file(self, file_path: str) -> Dict:
        """
        Parse a Discord export file (JSON or CSV).
        
        Args:
            file_path: Path to the exported chat file
            
        Returns:
            Dict with messages, your_messages, and conversation_pairs
        """
        if file_path.endswith('.json'):
            return self._parse_json(file_path)
        elif file_path.endswith('.csv'):
            return self._parse_csv(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")
    
    def _parse_json(self, file_path: str) -> Dict:
        """Parse JSON export from DiscordChatExporter."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        messages = []
        
        for msg in data.get('messages', []):
            # Skip bot messages if needed
            author = msg.get('author', {})
            if author.get('isBot', False):
                continue
            
            content = msg.get('content', '')
            if not content or self._should_skip(content):
                continue
            
            is_you = self._is_your_message(author)
            
            messages.append({
                'timestamp': msg.get('timestamp', ''),
                'sender': author.get('name', 'Unknown'),
                'sender_id': author.get('id', ''),
                'content': content,
                'is_you': is_you
            })
        
        # Sort by timestamp
        messages.sort(key=lambda x: x['timestamp'])
        
        your_messages = [m for m in messages if m['is_you']]
        conversation_pairs = self._extract_conversation_pairs(messages)
        
        return {
            'total_messages': len(messages),
            'your_messages': len(your_messages),
            'messages': messages,
            'conversation_pairs': conversation_pairs,
            'your_texts': [m['content'] for m in your_messages]
        }
    
    def _parse_csv(self, file_path: str) -> Dict:
        """Parse CSV export from DiscordChatExporter."""
        messages = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                content = row.get('Content', '')
                if not content or self._should_skip(content):
                    continue
                
                author_name = row.get('Author', 'Unknown')
                author_id = row.get('AuthorID', '')
                
                is_you = self._is_your_message_by_fields(author_id, author_name)
                
                messages.append({
                    'timestamp': row.get('Date', ''),
                    'sender': author_name,
                    'sender_id': author_id,
                    'content': content,
                    'is_you': is_you
                })
        
        your_messages = [m for m in messages if m['is_you']]
        conversation_pairs = self._extract_conversation_pairs(messages)
        
        return {
            'total_messages': len(messages),
            'your_messages': len(your_messages),
            'messages': messages,
            'conversation_pairs': conversation_pairs,
            'your_texts': [m['content'] for m in your_messages]
        }
    
    def _is_your_message(self, author: Dict) -> bool:
        """Check if a message was sent by you (JSON format)."""
        author_id = author.get('id', '')
        author_name = author.get('name', '').lower()
        
        return self._is_your_message_by_fields(author_id, author_name)
    
    def _is_your_message_by_fields(self, author_id: str, author_name: str) -> bool:
        """Check if a message was sent by you using ID and name."""
        if self.your_user_id and author_id == self.your_user_id:
            return True
        
        if self.your_username:
            author_name_lower = author_name.lower() if author_name else ''
            if self.your_username in author_name_lower:
                return True
        
        return False
    
    def _should_skip(self, content: str) -> bool:
        """Check if a message should be skipped."""
        skip_patterns = [
            r'^https?://',  # Just links
            r'^\s*$',  # Empty
            r'^\[.+\]$',  # Just embeds
        ]
        
        for pattern in skip_patterns:
            if re.match(pattern, content.strip()):
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
                # Find the previous non-you messages as context
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
    
    def parse_content(self, content: str, format_type: str = 'json') -> Dict:
        """
        Parse Discord chat content directly.
        
        Args:
            content: The raw export content
            format_type: 'json' or 'csv'
            
        Returns:
            Dict with parsed data
        """
        if format_type == 'json':
            data = json.loads(content)
            # Create temp structure and process
            messages = []
            for msg in data.get('messages', []):
                author = msg.get('author', {})
                if author.get('isBot', False):
                    continue
                
                msg_content = msg.get('content', '')
                if not msg_content or self._should_skip(msg_content):
                    continue
                
                messages.append({
                    'timestamp': msg.get('timestamp', ''),
                    'sender': author.get('name', 'Unknown'),
                    'sender_id': author.get('id', ''),
                    'content': msg_content,
                    'is_you': self._is_your_message(author)
                })
            
            messages.sort(key=lambda x: x['timestamp'])
            your_messages = [m for m in messages if m['is_you']]
            conversation_pairs = self._extract_conversation_pairs(messages)
            
            return {
                'total_messages': len(messages),
                'your_messages': len(your_messages),
                'messages': messages,
                'conversation_pairs': conversation_pairs,
                'your_texts': [m['content'] for m in your_messages]
            }
        
        raise ValueError(f"Unsupported format type: {format_type}")

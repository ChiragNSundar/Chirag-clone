"""
Discord Chat Parser - Parses exported Discord chat files.
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
        """
        try:
            if file_path.endswith('.json'):
                return self._parse_json(file_path)
            elif file_path.endswith('.csv'):
                return self._parse_csv(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_path}")
        except Exception as e:
            print(f"Error parsing Discord file {file_path}: {e}")
            return {'total_messages': 0, 'your_messages': 0, 'messages': [], 'conversation_pairs': [], 'your_texts': []}
    
    def _parse_json(self, file_path: str) -> Dict:
        """Parse JSON export from DiscordChatExporter."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"Invalid JSON in {file_path}")
            return self._empty_result()
        
        messages = []
        
        for msg in data.get('messages', []):
            author = msg.get('author', {})
            if author.get('isBot', False):
                continue
            
            content = msg.get('content', '')
            
            # Handle attachments - add placeholder if content is empty but has attachments
            if not content and msg.get('attachments'):
                content = "[Attachment]"
            
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
        
        return self._process_messages(messages)
    
    def _parse_csv(self, file_path: str) -> Dict:
        """Parse CSV export from DiscordChatExporter."""
        messages = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    content = row.get('Content', '')
                    attachments = row.get('Attachments', '')
                    
                    if not content and attachments:
                        content = "[Attachment]"
                    
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
        except Exception as e:
            print(f"CSV parsing error: {e}")
            return self._empty_result()
            
        return self._process_messages(messages)

    def _process_messages(self, messages: List[Dict]) -> Dict:
        """Common processing for messages."""
        # Sort by timestamp usually helps, though exports are generally sorted
        try:
            messages.sort(key=lambda x: x['timestamp'])
        except:
            pass # Ignore sort errors if timestamps are weird
            
        your_messages = [m for m in messages if m['is_you']]
        conversation_pairs = self._extract_conversation_pairs(messages)
        
        return {
            'total_messages': len(messages),
            'your_messages': len(your_messages),
            'messages': messages,
            'conversation_pairs': conversation_pairs,
            'your_texts': [m['content'] for m in your_messages]
        }
    
    def _empty_result(self) -> Dict:
        return {'total_messages': 0, 'your_messages': 0, 'messages': [], 'conversation_pairs': [], 'your_texts': []}
    
    def _is_your_message(self, author: Dict) -> bool:
        """Check if a message was sent by you (JSON format)."""
        author_id = author.get('id', '')
        author_name = author.get('name', '').lower()
        return self._is_your_message_by_fields(author_id, author_name)
    
    def _is_your_message_by_fields(self, author_id: str, author_name: str) -> bool:
        """Check if a message was sent by you using ID and name."""
        if self.your_user_id and str(author_id) == str(self.your_user_id):
            return True
        
        if self.your_username:
            author_name_lower = str(author_name).lower()
            if self.your_username in author_name_lower:
                return True
        
        return False
    
    def _should_skip(self, content: str) -> bool:
        """Check if a message should be skipped."""
        # Pre-compile these if this method is hot, but for now simple checking is fine
        content = content.strip()
        
        if not content:
            return True
            
        # Skip just URLs
        if re.match(r'^https?://\S+$', content):
            return True
            
        # Skip discord system messages often found in exports
        if content.startswith('Joined the server') or content.startswith('Left the server'):
            return True
            
        return False
    
    def _extract_conversation_pairs(self, messages: List[Dict]) -> List[Tuple[str, str]]:
        """
        Extract context-response pairs.
        Uses a sliding window approach for better context.
        """
        pairs = []
        
        for i, msg in enumerate(messages):
            if msg['is_you'] and i > 0:
                # Find previous block of non-you messages
                context_parts = []
                j = i - 1
                
                # Skip consecutive 'you' messages to find the trigger
                while j >= 0 and messages[j]['is_you']:
                    j -= 1
                    
                if j < 0:
                    continue
                
                # Collect context
                while j >= 0 and len(context_parts) < 3:
                    if messages[j]['is_you']:
                        break
                    context_parts.insert(0, messages[j]['content'])
                    j -= 1
                
                if context_parts:
                    context = ' | '.join(context_parts)
                    pairs.append((context, msg['content']))
        
        return pairs
    
    def parse_content(self, content: str, format_type: str = 'json') -> Dict:
        """Parse raw content string."""
        if format_type == 'json':
            try:
                data = json.loads(content)
                # Re-use the JSON logic by saving to temp or refactoring
                # For simplicity here, we duplicate logic slightly or mock file read behavior
                # but better to assume this is rarely called directly compared to parse_file
                
                # Logic copied from _parse_json but adapted for dict input
                messages = []
                for msg in data.get('messages', []):
                    author = msg.get('author', {})
                    if author.get('isBot', False): continue
                    
                    content = msg.get('content', '')
                    if not content and msg.get('attachments'): content = "[Attachment]"
                    
                    if not content or self._should_skip(content): continue
                    
                    messages.append({
                        'timestamp': msg.get('timestamp', ''),
                        'sender': author.get('name', 'Unknown'),
                        'sender_id': author.get('id', ''),
                        'content': content,
                        'is_you': self._is_your_message(author)
                    })
                return self._process_messages(messages)
            except json.JSONDecodeError:
                return self._empty_result()
        
        raise ValueError(f"Unsupported format type: {format_type}")

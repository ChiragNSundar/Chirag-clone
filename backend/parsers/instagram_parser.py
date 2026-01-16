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
        """Parse an Instagram messages JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return self.parse_data(data)
        except Exception as e:
            print(f"Error parsing Instagram file {file_path}: {e}")
            return self._empty_result()
    
    def parse_data(self, data: Dict) -> Dict:
        """Parse Instagram messages data structure."""
        messages = []
        
        for msg in data.get('messages', []):
            content = msg.get('content', '')
            
            # Handle media only messages
            if not content:
                if msg.get('photos') or msg.get('videos'):
                    content = "[Media]"
                elif msg.get('audio_files'):
                    content = "[Audio]"
                elif msg.get('share'):
                    content = "[Shared Post]"
            
            # Skip empty or invalid content
            if not content or self._should_skip(msg, content):
                continue
            
            content = self._fix_encoding(content)
            sender = self._fix_encoding(msg.get('sender_name', 'Unknown'))
            
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
        
        # Instagram exports are in reverse chronological order
        messages.reverse()
        
        # Sort just in case
        messages.sort(key=lambda x: x.get('timestamp_ms', 0))
        
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
    
    def _fix_encoding(self, text: str) -> str:
        """Fix Instagram's broken UTF-8 encoding (mojibake)."""
        if not text:
            return ""
        try:
            # Common Instagram export issue: UTF-8 bytes interpreted as Latin-1
            return text.encode('latin1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            return text
    
    def parse_content(self, content: str) -> Dict:
        """Parse Instagram JSON content directly."""
        try:
            data = json.loads(content)
            return self.parse_data(data)
        except json.JSONDecodeError:
            return self._empty_result()
    
    def _empty_result(self) -> Dict:
        return {
            'total_messages': 0, 'your_messages': 0, 'messages': [], 
            'conversation_pairs': [], 'your_texts': [], 'participants': []
        }
    
    def _is_your_message(self, sender: str) -> bool:
        """Check if a message was sent by you."""
        sender_lower = sender.lower().strip()
        
        if sender_lower == self.your_username:
            return True
        
        if self.your_username in sender_lower:
            return True
        
        return False
    
    def _should_skip(self, msg: Dict, content: str) -> bool:
        """Check if a message should be skipped."""
        msg_type = msg.get('type', '')
        
        # Skip calls and notifications
        if msg_type in ['Call', 'VideoCall']:
            return True
            
        # Skip reactions if that's all there is
        if 'reactions' in msg and not content:
            return True
            
        # Skip generic generic empty messages
        if not content.strip():
            return True
        
        return False
    
    def _extract_conversation_pairs(self, messages: List[Dict]) -> List[Tuple[str, str]]:
        """Extract context-response pairs where you responded."""
        pairs = []
        
        for i, msg in enumerate(messages):
            if msg['is_you'] and i > 0:
                # Find previous non-you messages as context
                context_parts = []
                j = i - 1
                
                # Skip consecutive 'you' messages
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
    
    def parse_inbox_folder(self, inbox_path: str) -> Dict:
        """Parse all conversation files in an Instagram inbox folder."""
        import os
        
        all_messages = []
        all_pairs = []
        all_your_texts = []
        
        if not os.path.exists(inbox_path):
            return self._empty_result()
            
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
                        if result['total_messages'] > 0:
                            all_messages.extend(result['messages'])
                            all_pairs.extend(result['conversation_pairs'])
                            all_your_texts.extend(result['your_texts'])
                    except Exception as e:
                        print(f"Error parsing {file_path}: {e}")
        
        # Re-sort combined messages if needed, though usually extensive
        # all_messages.sort(key=lambda x: x.get('timestamp_ms', 0))
        
        your_messages = [m for m in all_messages if m['is_you']]
        
        return {
            'total_messages': len(all_messages),
            'your_messages': len(your_messages),
            'messages': all_messages,
            'conversation_pairs': all_pairs,
            'your_texts': all_your_texts
        }

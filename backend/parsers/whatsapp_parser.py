"""
WhatsApp Chat Parser - Parses exported WhatsApp chat files.
"""
import re
from typing import List, Tuple, Dict, Optional
from datetime import datetime


class WhatsAppParser:
    """Parser for WhatsApp chat exports."""
    
    # Common WhatsApp export formats
    PATTERNS = [
        # Format: [DD/MM/YY, HH:MM:SS] Name: Message
        r'\[(\d{1,2}/\d{1,2}/\d{2,4}),?\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]\s*([^:]+):\s*(.*)',
        # Format: DD/MM/YY, HH:MM - Name: Message
        r'(\d{1,2}/\d{1,2}/\d{2,4}),?\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s*-\s*([^:]+):\s*(.*)',
        # Format: MM/DD/YY, HH:MM - Name: Message (US format)
        r'(\d{1,2}/\d{1,2}/\d{2,4}),?\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s*-\s*([^:]+):\s*(.*)',
    ]
    
    # Messages to skip
    SKIP_PATTERNS = [
        r'<Media omitted>',
        r'<image omitted>',
        r'<video omitted>',
        r'<audio omitted>',
        r'<sticker omitted>',
        r'<GIF omitted>',
        r'<Contact card omitted>',
        r'<document omitted>',
        r'Missed voice call',
        r'Missed video call',
        r'deleted this message',
        r'This message was deleted',
        r'You deleted this message',
        r'Messages and calls are end-to-end encrypted',
        r'created group',
        r'added you',
        r'left the group',
        r'changed the subject',
        r'changed this group\'s icon',
        r'changed the group description',
    ]
    
    def __init__(self, your_name: str):
        """
        Initialize the parser.
        
        Args:
            your_name: Your name as it appears in the chat export
        """
        self.your_name = your_name
    
    def parse_file(self, file_path: str) -> Dict:
        """
        Parse a WhatsApp export file.
        
        Args:
            file_path: Path to the exported chat file
            
        Returns:
            Dict with messages, your_messages, and conversation_pairs
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.parse_content(content)
    
    def parse_content(self, content: str) -> Dict:
        """
        Parse WhatsApp chat content.
        
        Args:
            content: The raw chat export text
            
        Returns:
            Dict with parsed data
        """
        messages = self._extract_messages(content)
        your_messages = [m for m in messages if m['is_you']]
        conversation_pairs = self._extract_conversation_pairs(messages)
        
        return {
            'total_messages': len(messages),
            'your_messages': len(your_messages),
            'messages': messages,
            'conversation_pairs': conversation_pairs,
            'your_texts': [m['content'] for m in your_messages]
        }
    
    def _extract_messages(self, content: str) -> List[Dict]:
        """Extract individual messages from the content."""
        messages = []
        lines = content.split('\n')
        
        current_message = None
        
        for line in lines:
            parsed = self._parse_line(line)
            
            if parsed:
                if current_message:
                    messages.append(current_message)
                current_message = parsed
            elif current_message and line.strip():
                # Continuation of previous message
                current_message['content'] += '\n' + line.strip()
        
        if current_message:
            messages.append(current_message)
        
        # Filter out system messages and media
        messages = [m for m in messages if not self._should_skip(m['content'])]
        
        return messages
    
    def _parse_line(self, line: str) -> Optional[Dict]:
        """Parse a single line to extract message data."""
        for pattern in self.PATTERNS:
            match = re.match(pattern, line.strip())
            if match:
                groups = match.groups()
                date_str = groups[0]
                time_str = groups[1]
                sender = groups[2].strip()
                content = groups[3].strip()
                
                # Check if this is your message
                is_you = self._is_your_message(sender)
                
                return {
                    'date': date_str,
                    'time': time_str,
                    'sender': sender,
                    'content': content,
                    'is_you': is_you
                }
        
        return None
    
    def _is_your_message(self, sender: str) -> bool:
        """Check if a message was sent by you."""
        sender_lower = sender.lower().strip()
        your_name_lower = self.your_name.lower().strip()
        
        # Direct match
        if sender_lower == your_name_lower:
            return True
        
        # Partial match (name might be saved differently)
        if your_name_lower in sender_lower or sender_lower in your_name_lower:
            return True
        
        # Common variations
        if sender_lower in ['you', 'me']:
            return True
        
        return False
    
    def _should_skip(self, content: str) -> bool:
        """Check if a message should be skipped."""
        for pattern in self.SKIP_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
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
                # Find the previous message(s) as context
                context_parts = []
                j = i - 1
                
                # Get up to 3 previous messages as context
                while j >= 0 and len(context_parts) < 3:
                    if not messages[j]['is_you']:
                        context_parts.insert(0, messages[j]['content'])
                    j -= 1
                
                if context_parts:
                    context = ' | '.join(context_parts)
                    pairs.append((context, msg['content']))
        
        return pairs

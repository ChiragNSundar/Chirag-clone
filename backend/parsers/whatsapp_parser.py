"""
WhatsApp Chat Parser - Parses exported WhatsApp chat files.
"""
import re
from typing import List, Tuple, Dict, Optional
from datetime import datetime


class WhatsAppParser:
    """Parser for WhatsApp chat exports."""
    
    # Compiled common WhatsApp export formats
    # Note: Using compiled regex for performance
    PATTERNS = [
        # Format: [DD/MM/YY, HH:MM:SS] Name: Message (iOS/modern)
        re.compile(r'^\[(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}),?\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]\s*([^:]+):\s*(.*)', re.IGNORECASE),
        # Format: DD/MM/YY, HH:MM - Name: Message (Android/classic)
        re.compile(r'^(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}),?\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s*-\s*([^:]+):\s*(.*)', re.IGNORECASE),
        # Format: YYYY-MM-DD, HH:MM - Name: Message
        re.compile(r'^(\d{4}[/.-]\d{1,2}[/.-]\d{1,2}),?\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s*-\s*([^:]+):\s*(.*)', re.IGNORECASE),
    ]
    
    # Messages to skip (system messages, encryption notices, etc.)
    SKIP_PATTERNS = [
        re.compile(r'<Media omitted>', re.IGNORECASE),
        re.compile(r'<image omitted>', re.IGNORECASE),
        re.compile(r'<video omitted>', re.IGNORECASE),
        re.compile(r'<audio omitted>', re.IGNORECASE),
        re.compile(r'<sticker omitted>', re.IGNORECASE),
        re.compile(r'<GIF omitted>', re.IGNORECASE),
        re.compile(r'<Contact card omitted>', re.IGNORECASE),
        re.compile(r'<document omitted>', re.IGNORECASE),
        re.compile(r'Missed voice call', re.IGNORECASE),
        re.compile(r'Missed video call', re.IGNORECASE),
        re.compile(r'deleted this message', re.IGNORECASE),
        re.compile(r'This message was deleted', re.IGNORECASE),
        re.compile(r'You deleted this message', re.IGNORECASE),
        re.compile(r'Messages and calls are end-to-end encrypted', re.IGNORECASE),
        re.compile(r'created group', re.IGNORECASE),
        re.compile(r'added you', re.IGNORECASE),
        re.compile(r'left the group', re.IGNORECASE),
        re.compile(r'changed the subject', re.IGNORECASE),
        re.compile(r'changed this group\'s icon', re.IGNORECASE),
        re.compile(r'changed the group description', re.IGNORECASE),
        re.compile(r'waiting for this message', re.IGNORECASE),
    ]
    
    # Control characters to strip (LTR/RTL marks often found in WhatsApp exports)
    CONTROL_CHARS = dict.fromkeys(range(0x200E, 0x2010), None)
    
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
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Fallback for older exports or different locales
            with open(file_path, 'r', encoding='utf-8-sig') as f:
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
        # Pre-clean content - remove BIDs and other control chars
        content = content.translate(self.CONTROL_CHARS)
        
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
            # Skip empty lines immediately
            if not line.strip():
                continue
                
            parsed = self._parse_line(line)
            
            if parsed:
                if current_message:
                    # Validate previous message before adding
                    if current_message['content'].strip():
                        messages.append(current_message)
                current_message = parsed
            elif current_message:
                # Continuation of previous message (multi-line)
                current_message['content'] += '\n' + line.strip()
        
        # Add final message
        if current_message and current_message['content'].strip():
            messages.append(current_message)
        
        # Filter out system messages and media using strict checking
        valid_messages = []
        for m in messages:
            cleaned_content = m['content'].strip()
            if cleaned_content and not self._should_skip(cleaned_content):
                m['content'] = cleaned_content
                valid_messages.append(m)
        
        return valid_messages
    
    def _parse_line(self, line: str) -> Optional[Dict]:
        """Parse a single line to extract message data."""
        # Fast fail if line is too short to contain timestamp
        if len(line) < 10:
            return None
            
        for pattern in self.PATTERNS:
            match = pattern.match(line.strip())
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
        
        # Exact match
        if sender_lower == your_name_lower:
            return True
        
        # Handle "You" (WhatsApp sometimes exports as "You")
        if sender_lower == "you":
            return True
            
        # Partial match if name is long (e.g. "Chirag Sundar" vs "Chirag")
        if len(your_name_lower) > 3 and (your_name_lower in sender_lower or sender_lower in your_name_lower):
            return True
        
        return False
    
    def _should_skip(self, content: str) -> bool:
        """Check if a message should be skipped."""
        for pattern in self.SKIP_PATTERNS:
            if pattern.search(content):
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
                # We want the immediate previous block from OTHER person
                
                # Scan backwards for non-you messages
                context_parts = []
                j = i - 1
                
                # Skip your own previous messages (consecutive messages)
                while j >= 0 and messages[j]['is_you']:
                    j -= 1
                
                if j < 0:
                    continue
                    
                # Now collect up to 3 messages from the other person
                while j >= 0 and len(context_parts) < 3:
                    if messages[j]['is_you']:
                        break # Stop if we hit another one of our messages
                    context_parts.insert(0, messages[j]['content'])
                    j -= 1
                
                if context_parts:
                    context = ' | '.join(context_parts)
                    pairs.append((context, msg['content']))
        
        return pairs

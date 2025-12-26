"""
Smart Parser - LLM-powered parser for unstructured text.
Extracts conversation pairs from messy, unformatted text.
"""
from typing import List, Tuple, Dict
import re


class SmartParser:
    """Parser that uses heuristics and LLM to extract Q&A pairs from any text."""
    
    # Common conversation indicators
    SPEAKER_PATTERNS = [
        r'^([A-Za-z0-9_]+)\s*:\s*(.+)$',  # "Name: message"
        r'^([A-Za-z0-9_]+)\s*>\s*(.+)$',  # "Name> message"
        r'^\[([A-Za-z0-9_]+)\]\s*(.+)$',  # "[Name] message"
        r'^<([A-Za-z0-9_]+)>\s*(.+)$',    # "<Name> message"
    ]
    
    def __init__(self, your_identifier: str = None):
        """
        Initialize parser.
        
        Args:
            your_identifier: Your name/username to identify your messages
        """
        self.your_identifier = your_identifier.lower() if your_identifier else None
    
    def parse_content(self, content: str) -> Dict:
        """
        Parse unstructured text content.
        
        Args:
            content: Raw text content (any format)
            
        Returns:
            Dict with messages and conversation pairs
        """
        # Try structured parsing first
        messages = self._try_structured_parse(content)
        
        if not messages:
            # Fall back to heuristic parsing
            messages = self._heuristic_parse(content)
        
        # Extract your messages
        your_messages = [m for m in messages if m.get('is_you', False)]
        
        # Create conversation pairs
        pairs = self._extract_pairs(messages)
        
        return {
            'total_messages': len(messages),
            'your_messages': len(your_messages),
            'messages': messages,
            'conversation_pairs': pairs,
            'your_texts': [m['content'] for m in your_messages]
        }
    
    def parse_with_llm(self, content: str, llm_service) -> Dict:
        """
        Use LLM to extract conversation pairs from very messy text.
        
        Args:
            content: Raw text content
            llm_service: LLM service for parsing
            
        Returns:
            Dict with extracted data
        """
        # Truncate if too long
        max_chars = 8000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n...(truncated)"
        
        prompt = f"""Extract conversation pairs from this text. The user's name/identifier is: {self.your_identifier or 'unknown'}

Find messages where someone says something and the user responds. Output as JSON array:
[{{"context": "what someone said to user", "response": "what user replied"}}]

Only include clear Q&A pairs. If you can identify the user's messages, include them.
If the format is unclear, do your best to extract meaningful exchanges.

TEXT:
{content}

JSON OUTPUT (just the array, no explanation):"""

        try:
            result = llm_service.generate_response(
                system_prompt="You are a conversation parser. Output only valid JSON.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            # Parse JSON from response
            import json
            
            # Clean up response - find JSON array
            result = result.strip()
            if result.startswith('```'):
                result = re.sub(r'^```\w*\n?', '', result)
                result = re.sub(r'\n?```$', '', result)
            
            pairs_data = json.loads(result)
            
            pairs = [(p['context'], p['response']) for p in pairs_data if 'context' in p and 'response' in p]
            
            return {
                'total_messages': len(pairs) * 2,
                'your_messages': len(pairs),
                'messages': [],
                'conversation_pairs': pairs,
                'your_texts': [p[1] for p in pairs],
                'parsed_by': 'llm'
            }
            
        except Exception as e:
            print(f"LLM parsing failed: {e}")
            # Fall back to heuristic
            return self.parse_content(content)
    
    def _try_structured_parse(self, content: str) -> List[Dict]:
        """Try to parse using common structured formats."""
        messages = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            for pattern in self.SPEAKER_PATTERNS:
                match = re.match(pattern, line)
                if match:
                    speaker = match.group(1).strip()
                    text = match.group(2).strip()
                    
                    is_you = False
                    if self.your_identifier:
                        speaker_lower = speaker.lower()
                        if (speaker_lower == self.your_identifier or 
                            self.your_identifier in speaker_lower or
                            speaker_lower in ['me', 'you', 'myself']):
                            is_you = True
                    
                    messages.append({
                        'sender': speaker,
                        'content': text,
                        'is_you': is_you
                    })
                    break
        
        return messages
    
    def _heuristic_parse(self, content: str) -> List[Dict]:
        """
        Parse using heuristics for completely unstructured text.
        Looks for alternating patterns, quotes, etc.
        """
        messages = []
        
        # Try to find quoted responses
        # Pattern: "question" -> "answer" or "question" "answer"
        quote_pattern = r'"([^"]+)"\s*(?:->|:|\n)\s*"([^"]+)"'
        matches = re.findall(quote_pattern, content)
        
        for q, a in matches:
            messages.append({'sender': 'other', 'content': q, 'is_you': False})
            messages.append({'sender': 'you', 'content': a, 'is_you': True})
        
        # If no quotes found, split by sentences and alternate
        if not messages:
            sentences = re.split(r'[.!?]+', content)
            sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
            
            for i, sentence in enumerate(sentences[:20]):  # Limit
                messages.append({
                    'sender': 'other' if i % 2 == 0 else 'you',
                    'content': sentence,
                    'is_you': i % 2 == 1
                })
        
        return messages
    
    def _extract_pairs(self, messages: List[Dict]) -> List[Tuple[str, str]]:
        """Extract context-response pairs."""
        pairs = []
        
        for i, msg in enumerate(messages):
            if msg.get('is_you', False) and i > 0:
                # Get previous non-you messages as context
                context_parts = []
                j = i - 1
                while j >= 0 and len(context_parts) < 3:
                    if not messages[j].get('is_you', False):
                        context_parts.insert(0, messages[j]['content'])
                    j -= 1
                
                if context_parts:
                    context = ' | '.join(context_parts)
                    pairs.append((context, msg['content']))
        
        return pairs

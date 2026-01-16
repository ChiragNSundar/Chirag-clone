"""
Smart Parser - LLM-powered parser for unstructured text.
Extracts conversation pairs from messy, unformatted text or direct copy-pastes.
"""
from typing import List, Tuple, Dict
import re
import json


class SmartParser:
    """Parser that uses heuristics and LLM to extract Q&A pairs from any text."""
    
    # Common conversation indicators
    SPEAKER_PATTERNS = [
        re.compile(r'^([A-Za-z0-9_ ]{1,20})\s*:\s*(.+)$'),        # "Name: message"
        re.compile(r'^([A-Za-z0-9_ ]{1,20})\s*>\s*(.+)$'),        # "Name> message"
        re.compile(r'^\[([A-Za-z0-9_ ]{1,20})\]\s*(.+)$'),        # "[Name] message"
        re.compile(r'^<([A-Za-z0-9_ ]{1,20})>\s*(.+)$'),          # "<Name> message"
        # Timestamped variations
        re.compile(r'^\[?\d{2}:\d{2}\]?\s*([A-Za-z0-9_ ]{1,20})\s*:\s*(.+)$'),  # "10:00 Name: message"
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
        # Clean basic copy-paste artifacts
        content = content.replace('\r\n', '\n').strip()
        
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
        Robustly handles LLM output issues.
        """
        # Truncate if too long (token limit safety)
        max_chars = 12000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n...(truncated)"
        
        prompt = f"""Extract meaningful conversation Q&A pairs from this text.
The user (me) is identified as: {self.your_identifier or 'unknown/implicit'}.

Format as a JSON ARRAY of objects:
[{{"context": "what was said to me", "response": "what I replied"}}]

Rules:
1. Ignore empty chatter or system messages.
2. Only include pairs where the user is clearly responding.
3. If user is unknown, infer from context (e.g. 'me', 'I').

TEXT:
{content}

JSON OUTPUT:"""

        try:
            result = llm_service.generate_response(
                system_prompt="You are a data extractor. Output ONLY valid JSON array.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            # Clean up response - find JSON array
            result_clean = self._clean_json_block(result)
            
            try:
                pairs_data = json.loads(result_clean)
            except json.JSONDecodeError:
                # Try simple repair - close brackets
                if result_clean.strip().startswith('[') and not result_clean.strip().endswith(']'):
                    pairs_data = json.loads(result_clean + ']')
                else:
                    raise
            
            if not isinstance(pairs_data, list):
                pairs_data = [] # Invalid format
            
            pairs = []
            for p in pairs_data:
                if isinstance(p, dict) and 'context' in p and 'response' in p:
                    pairs.append((str(p['context']), str(p['response'])))
            
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
    
    def _clean_json_block(self, text: str) -> str:
        """Extract JSON block from markdown or mess text."""
        text = text.strip()
        # Remove markdown code block
        if text.startswith('```'):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
        
        # Find first [ and last ]
        start = text.find('[')
        end = text.rfind(']')
        
        if start != -1 and end != -1:
            return text[start:end+1]
        return text
    
    def _try_structured_parse(self, content: str) -> List[Dict]:
        """Try to parse using common structured formats."""
        messages = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            for pattern in self.SPEAKER_PATTERNS:
                match = pattern.match(line)
                if match:
                    if len(match.groups()) == 2:
                        speaker = match.group(1).strip()
                        text = match.group(2).strip()
                        
                        is_you = self._check_is_you(speaker)
                        
                        messages.append({
                            'sender': speaker,
                            'content': text,
                            'is_you': is_you
                        })
                        break
        
        return messages
    
    def _check_is_you(self, speaker: str) -> bool:
        """Check if speaker is the user."""
        if not self.your_identifier:
            return False
            
        speaker_lower = speaker.lower()
        if (speaker_lower == self.your_identifier or 
            self.your_identifier in speaker_lower or
            speaker_lower in ['me', 'you', 'myself']):
            return True
        return False
    
    def _heuristic_parse(self, content: str) -> List[Dict]:
        """
        Parse using heuristics for completely unstructured text.
        """
        messages = []
        
        # Try quoted "Q" -> "A" pattern
        quote_pattern = r'"([^"]+)"\s*(?:->|:|\n)\s*"([^"]+)"'
        matches = re.findall(quote_pattern, content)
        
        for q, a in matches:
            messages.append({'sender': 'other', 'content': q, 'is_you': False})
            messages.append({'sender': 'you', 'content': a, 'is_you': True})
            
        if matches:
            return messages
        
        # Fallback: Split by lines, assume alternating
        lines = [line.strip() for line in content.split('\n') if len(line.strip()) > 2]
        
        # Heuristic: If lines look like "User: Message", skip heuristic
        if any(':' in line for line in lines[:5]):
            return [] # Let structured parse handle it (or fail)
        
        # Otherwise, assume strict alternation
        for i, line in enumerate(lines):
            # Simple alternating logic
            is_you = (i % 2 != 0) # Assume user is second
            messages.append({
                'sender': 'other' if not is_you else 'you',
                'content': line,
                'is_you': is_you
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
                
                # Skip consecutive user messages
                while j >= 0 and messages[j].get('is_you', False):
                    j -= 1
                
                if j < 0:
                    continue
                    
                while j >= 0 and len(context_parts) < 3:
                    if messages[j].get('is_you', False):
                        break
                    context_parts.insert(0, messages[j]['content'])
                    j -= 1
                
                if context_parts:
                    context = ' | '.join(context_parts)
                    pairs.append((context, msg['content']))
        
        return pairs

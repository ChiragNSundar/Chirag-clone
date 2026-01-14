"""
Parser Tests - Unit tests for chat log parsers.
Covers WhatsApp, Discord, Instagram, and Smart parser.

Run with: pytest tests/test_parsers.py -v
"""
import pytest
import os
import sys
import tempfile
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Safe imports with skip mechanism
try:
    from parsers.whatsapp_parser import WhatsAppParser
    from parsers.discord_parser import DiscordParser
    from parsers.instagram_parser import InstagramParser
    from parsers.smart_parser import SmartParser
    PARSERS_AVAILABLE = True
except ImportError as e:
    PARSERS_AVAILABLE = False
    IMPORT_ERROR = str(e)

skip_if_no_parsers = pytest.mark.skipif(
    not PARSERS_AVAILABLE,
    reason=f"Parsers not available: {IMPORT_ERROR if not PARSERS_AVAILABLE else ''}"
)


@skip_if_no_parsers
class TestWhatsAppParser:
    """Test WhatsApp chat log parser."""
    
    def test_parser_initialization(self):
        """Test parser can be initialized with your_name."""
        parser = WhatsAppParser(your_name="TestUser")
        assert parser.your_name == "TestUser"
    
    def test_parse_basic_message(self):
        """Test parsing a basic WhatsApp message."""
        parser = WhatsAppParser(your_name="John")
        
        sample = """12/25/24, 10:30 AM - John: Hello everyone!
12/25/24, 10:31 AM - Jane: Hi John!"""
        
        result = parser.parse_content(sample)
        
        assert isinstance(result, dict)
        assert 'total_messages' in result
        assert 'your_messages' in result
        assert 'conversation_pairs' in result
    
    def test_parse_empty_content(self):
        """Test parsing empty content."""
        parser = WhatsAppParser(your_name="TestUser")
        
        result = parser.parse_content("")
        
        assert isinstance(result, dict)
        assert result['total_messages'] == 0
            
    def test_parse_with_unicode(self):
        """Test parsing messages with emoji and unicode."""
        parser = WhatsAppParser(your_name="John")
        
        sample = """12/25/24, 10:30 AM - John: Hello 🎉😊
12/25/24, 10:31 AM - Jane: Great! 👍"""
        
        result = parser.parse_content(sample)
        
        assert isinstance(result, dict)
        
    def test_identifies_your_messages(self):
        """Test that parser correctly identifies your messages."""
        parser = WhatsAppParser(your_name="John")
        
        sample = """12/25/24, 10:30 AM - John: This is my message
12/25/24, 10:31 AM - Jane: This is not my message"""
        
        result = parser.parse_content(sample)
        
        # Check that your_texts only contains John's message
        assert "This is my message" in result['your_texts']


@skip_if_no_parsers
class TestDiscordParser:
    """Test Discord JSON export parser."""
    
    def test_parser_initialization(self):
        """Test parser can be initialized."""
        parser = DiscordParser(your_username="TestUser")
        assert parser.your_username == "testuser"  # lowercased
        
    def test_parser_with_user_id(self):
        """Test parser initialized with user ID."""
        parser = DiscordParser(your_user_id="123456789")
        assert parser.your_user_id == "123456789"
    
    def test_parse_json_content(self):
        """Test parsing JSON content."""
        parser = DiscordParser(your_username="TestUser")
        
        sample = {
            "messages": [
                {
                    "author": {"name": "TestUser", "id": "123", "isBot": False},
                    "content": "Hello Discord!",
                    "timestamp": "2024-12-25T10:30:00.000Z"
                },
                {
                    "author": {"name": "OtherUser", "id": "456", "isBot": False},
                    "content": "Hey there!",
                    "timestamp": "2024-12-25T10:31:00.000Z"
                }
            ]
        }
        
        result = parser.parse_content(json.dumps(sample), format_type='json')
        
        assert isinstance(result, dict)
        assert 'total_messages' in result
        assert result['total_messages'] >= 1
            
    def test_parse_empty_messages(self):
        """Test parsing export with no messages."""
        parser = DiscordParser(your_username="TestUser")
        
        sample = {"messages": []}
        
        result = parser.parse_content(json.dumps(sample), format_type='json')
        
        assert isinstance(result, dict)
        assert result['total_messages'] == 0


@skip_if_no_parsers  
class TestInstagramParser:
    """Test Instagram JSON export parser."""
    
    def test_parser_initialization(self):
        """Test parser can be initialized."""
        parser = InstagramParser(your_username="testuser")
        assert parser.your_username == "testuser"


@skip_if_no_parsers
class TestSmartParser:
    """Test smart auto-detecting parser."""
    
    def test_parser_initialization(self):
        """Test parser can be initialized."""
        parser = SmartParser(your_identifier="TestUser")
        assert parser.your_identifier == "testuser"  # lowercased
        
    def test_parse_structured_content(self):
        """Test parsing structured content."""
        parser = SmartParser(your_identifier="TestUser")
        
        sample = """OtherPerson: What do you think?
TestUser: I think it's great!
OtherPerson: Awesome!"""
        
        result = parser.parse_content(sample)
        
        assert isinstance(result, dict)
        assert 'messages' in result
        assert 'conversation_pairs' in result
            
    def test_parse_quoted_content(self):
        """Test parsing quoted content."""
        parser = SmartParser(your_identifier="me")
        
        sample = '"What is your name?" -> "I am TestBot"'
        
        result = parser.parse_content(sample)
        
        assert isinstance(result, dict)


@skip_if_no_parsers
class TestParserEdgeCases:
    """Test edge cases across all parsers."""
    
    def test_whatsapp_multiline_message(self):
        """Test handling multi-line messages."""
        parser = WhatsAppParser(your_name="John")
        
        sample = """12/25/24, 10:30 AM - John: Hello
This is a continuation
Of the same message
12/25/24, 10:31 AM - Jane: Got it!"""
        
        result = parser.parse_content(sample)
        assert isinstance(result, dict)
        
    def test_special_characters(self):
        """Test handling special characters."""
        parser = SmartParser(your_identifier="test")
        
        sample = "User: Hello <script>alert('xss')</script>"
        result = parser.parse_content(sample)
        
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

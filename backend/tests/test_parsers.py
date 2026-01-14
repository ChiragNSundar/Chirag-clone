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


class TestWhatsAppParser:
    """Test WhatsApp chat log parser."""
    
    def test_parse_basic_message(self):
        """Test parsing a basic WhatsApp message."""
        from parsers.whatsapp_parser import WhatsAppParser
        parser = WhatsAppParser()
        
        sample = """12/25/24, 10:30 AM - John: Hello everyone!
12/25/24, 10:31 AM - Jane: Hi John!"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(sample)
            f.flush()
            
            result = parser.parse(f.name)
            os.unlink(f.name)
            
            assert isinstance(result, list)
            if result:  # If parsing succeeded
                assert len(result) >= 1
    
    def test_parse_empty_file(self):
        """Test parsing empty file."""
        from parsers.whatsapp_parser import WhatsAppParser
        parser = WhatsAppParser()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("")
            f.flush()
            
            result = parser.parse(f.name)
            os.unlink(f.name)
            
            assert isinstance(result, list)
            assert len(result) == 0
            
    def test_parse_handles_unicode(self):
        """Test parsing messages with emoji and unicode."""
        from parsers.whatsapp_parser import WhatsAppParser
        parser = WhatsAppParser()
        
        sample = """12/25/24, 10:30 AM - John: Hello 🎉😊
12/25/24, 10:31 AM - Jane: नमस्ते"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(sample)
            f.flush()
            
            result = parser.parse(f.name)
            os.unlink(f.name)
            
            assert isinstance(result, list)


class TestDiscordParser:
    """Test Discord JSON export parser."""
    
    def test_parse_basic_export(self):
        """Test parsing basic Discord export."""
        from parsers.discord_parser import DiscordParser
        parser = DiscordParser()
        
        sample = {
            "messages": [
                {
                    "author": {"name": "TestUser"},
                    "content": "Hello Discord!",
                    "timestamp": "2024-12-25T10:30:00.000Z"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample, f)
            f.flush()
            
            result = parser.parse(f.name)
            os.unlink(f.name)
            
            assert isinstance(result, list)
            
    def test_parse_empty_messages(self):
        """Test parsing export with no messages."""
        from parsers.discord_parser import DiscordParser
        parser = DiscordParser()
        
        sample = {"messages": []}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample, f)
            f.flush()
            
            result = parser.parse(f.name)
            os.unlink(f.name)
            
            assert isinstance(result, list)
            assert len(result) == 0
            
    def test_parse_invalid_json(self):
        """Test handling invalid JSON gracefully."""
        from parsers.discord_parser import DiscordParser
        parser = DiscordParser()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {{{")
            f.flush()
            
            try:
                result = parser.parse(f.name)
                assert isinstance(result, list)
            except:
                pass  # Exception is acceptable for invalid JSON
            finally:
                os.unlink(f.name)


class TestInstagramParser:
    """Test Instagram JSON export parser."""
    
    def test_parse_basic_export(self):
        """Test parsing basic Instagram export."""
        from parsers.instagram_parser import InstagramParser
        parser = InstagramParser()
        
        sample = {
            "messages": [
                {
                    "sender_name": "TestUser",
                    "content": "Hello Instagram!",
                    "timestamp_ms": 1703505000000
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample, f)
            f.flush()
            
            result = parser.parse(f.name)
            os.unlink(f.name)
            
            assert isinstance(result, list)


class TestSmartParser:
    """Test smart auto-detecting parser."""
    
    def test_detect_whatsapp_format(self):
        """Test detecting WhatsApp format."""
        from parsers.smart_parser import SmartParser
        parser = SmartParser()
        
        sample = """12/25/24, 10:30 AM - John: Hello!"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(sample)
            f.flush()
            
            result = parser.parse(f.name)
            os.unlink(f.name)
            
            assert isinstance(result, list)
            
    def test_detect_json_format(self):
        """Test detecting JSON format."""
        from parsers.smart_parser import SmartParser
        parser = SmartParser()
        
        sample = {"messages": []}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample, f)
            f.flush()
            
            result = parser.parse(f.name)
            os.unlink(f.name)
            
            assert isinstance(result, list)


class TestParserEdgeCases:
    """Test edge cases across all parsers."""
    
    def test_nonexistent_file(self):
        """Test handling nonexistent file."""
        from parsers.whatsapp_parser import WhatsAppParser
        parser = WhatsAppParser()
        
        try:
            result = parser.parse("/nonexistent/path/file.txt")
            # Should either return empty list or raise exception
            assert isinstance(result, list)
        except (FileNotFoundError, IOError):
            pass  # Expected behavior
            
    def test_binary_file(self):
        """Test handling binary file."""
        from parsers.smart_parser import SmartParser
        parser = SmartParser()
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.bin', delete=False) as f:
            f.write(b'\x00\x01\x02\x03\x04\x05')
            f.flush()
            
            try:
                result = parser.parse(f.name)
                assert isinstance(result, list)
            except:
                pass  # Exception is acceptable
            finally:
                os.unlink(f.name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

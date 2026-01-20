"""
Export/Import Tests - Unit tests for brain export/import functionality.

Run with: python -m pytest tests/test_export_import.py -v
"""
import pytest
import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Memory Service Export/Import Tests
# ============================================================================

class TestMemoryServiceExport:
    """Test memory service export functionality."""
    
    @pytest.fixture
    def memory_service(self):
        """Create memory service for testing."""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "memory_service",
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "services", "memory_service.py")
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.MemoryService()  # Create fresh instance for testing
        except Exception as e:
            pytest.skip(f"MemoryService not available: {e}")
    
    def test_export_returns_list(self, memory_service):
        """Test that export_all_training_examples returns a list."""
        result = memory_service.export_all_training_examples()
        assert isinstance(result, list)
    
    def test_export_contains_expected_fields(self, memory_service):
        """Test that exported examples have expected fields."""
        # Add a test example first
        memory_service.add_training_example(
            context="Test context for export",
            response="Test response for export",
            source="test"
        )
        
        result = memory_service.export_all_training_examples()
        assert len(result) > 0
        
        # Check first example has required fields
        example = result[0]
        assert 'context' in example
        assert 'response' in example
        assert 'source' in example
        assert 'timestamp' in example
    
    def test_import_returns_count(self, memory_service):
        """Test that import returns count of imported examples."""
        examples = [
            {"context": "Import test 1", "response": "Response 1", "source": "test"},
            {"context": "Import test 2", "response": "Response 2", "source": "test"},
        ]
        
        count = memory_service.import_training_examples(examples)
        assert count == 2
    
    def test_import_empty_list(self, memory_service):
        """Test that importing empty list returns 0."""
        count = memory_service.import_training_examples([])
        assert count == 0
    
    def test_export_import_roundtrip(self, memory_service):
        """Test that export followed by import preserves data."""
        # Add some examples
        memory_service.add_training_example("Context A", "Response A", "test")
        memory_service.add_training_example("Context B", "Response B", "test")
        
        # Export
        exported = memory_service.export_all_training_examples()
        initial_count = len(exported)
        
        # Clear and import
        memory_service.clear_training_data()
        imported_count = memory_service.import_training_examples(exported)
        
        # Verify
        assert imported_count == initial_count


# ============================================================================
# Personality Service Export/Import Tests
# ============================================================================

class TestPersonalityServiceExport:
    """Test personality service export functionality."""
    
    @pytest.fixture
    def personality_service(self):
        """Create personality service for testing."""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "personality_service",
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "services", "personality_service.py")
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.get_personality_service()
        except Exception as e:
            pytest.skip(f"PersonalityService not available: {e}")
    
    def test_export_returns_dict(self, personality_service):
        """Test that export_profile returns a dictionary."""
        result = personality_service.export_profile()
        assert isinstance(result, dict)
    
    def test_export_contains_all_fields(self, personality_service):
        """Test that exported profile has all expected fields."""
        result = personality_service.export_profile()
        
        expected_fields = [
            'name', 'common_phrases', 'emoji_patterns', 'vocabulary',
            'avg_message_length', 'typing_quirks', 'tone_markers',
            'facts', 'response_examples'
        ]
        
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"
    
    def test_export_facts_not_truncated(self, personality_service):
        """Test that facts are not truncated in export."""
        # Add facts
        for i in range(5):
            personality_service.add_fact(f"Test fact {i}")
        
        result = personality_service.export_profile()
        assert len(result['facts']) >= 5
    
    def test_import_merge_mode(self, personality_service):
        """Test that import in merge mode adds to existing data."""
        initial_facts = len(personality_service.get_profile().facts)
        
        import_data = {
            'facts': ['Imported fact A', 'Imported fact B'],
            'typing_quirks': ['lol', 'bruh']
        }
        
        personality_service.import_profile(import_data, merge=True)
        
        profile = personality_service.get_profile()
        # Should have original facts plus new ones (minus duplicates)
        assert len(profile.facts) >= initial_facts
    
    def test_import_replace_mode(self, personality_service):
        """Test that import in replace mode replaces data."""
        import_data = {
            'name': 'TestImport',
            'facts': ['Only this fact'],
            'common_phrases': [],
            'emoji_patterns': {},
            'vocabulary': {},
            'avg_message_length': 0,
            'typing_quirks': [],
            'tone_markers': {'casual': 0.5, 'formal': 0.5},
            'response_examples': []
        }
        
        personality_service.import_profile(import_data, merge=False)
        
        profile = personality_service.get_profile()
        assert profile.name == 'TestImport'


# ============================================================================
# Export Format Tests
# ============================================================================

class TestExportFormat:
    """Test export format structure and versioning."""
    
    def test_format_version_exists(self):
        """Test that export format can include version."""
        export_data = {
            "format_version": "1.0",
            "app_name": "Chirag-clone",
            "exported_at": datetime.now().isoformat(),
            "metadata": {},
            "personality_profile": {},
            "training_examples": []
        }
        
        assert export_data['format_version'] == '1.0'
        assert 'exported_at' in export_data
    
    def test_format_is_json_serializable(self):
        """Test that export format can be serialized to JSON."""
        export_data = {
            "format_version": "1.0",
            "app_name": "Chirag-clone",
            "exported_at": datetime.now().isoformat(),
            "metadata": {
                "total_training_examples": 10,
                "total_facts": 5
            },
            "personality_profile": {
                "name": "Test",
                "facts": ["Fact 1", "Fact 2"]
            },
            "training_examples": [
                {"context": "Hi", "response": "Hello"}
            ]
        }
        
        # Should not raise
        json_str = json.dumps(export_data)
        assert len(json_str) > 0
        
        # Should be parseable
        parsed = json.loads(json_str)
        assert parsed['format_version'] == '1.0'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

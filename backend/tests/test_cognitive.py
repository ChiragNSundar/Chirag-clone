"""
Tests for Cognitive Services (Memory, Notion, Briefing).
"""
import pytest
from unittest.mock import Mock, patch

# ============= Daily Briefing Tests =============

def test_daily_briefing_generation():
    """Test generating briefing text."""
    pytest.skip("daily_briefing_service removed - skipping test")



# ============= Memory Editing Tests =============

@pytest.mark.asyncio
async def test_memory_editing_endpoints():
    """Test edit and merge API endpoints."""
    from routes.cognitive import edit_memory, merge_memories, MemoryEditRequest, MemoryMergeRequest
    
    # Mock Services
    with patch('routes.cognitive._get_core_memory_service') as mock_get_service:
        mock_service = Mock()
        mock_get_service.return_value = mock_service
        
        # Test Edit
        mock_service.update_core_memory.return_value = True
        result = await edit_memory("mem_1", MemoryEditRequest(content="New Content"))
        
        assert result['success'] is True
        mock_service.update_core_memory.assert_called_with(
            memory_id="mem_1",
            content="New Content",
            category=None
        )
        
        # Test Merge
        mock_service.add_core_memory.return_value = {"id": "new_mem"}
        result = await merge_memories(MemoryMergeRequest(
            memory_ids=["mem_1", "mem_2"],
            merged_content="Merged Content"
        ))
        
        assert result['success'] is True
        assert mock_service.delete_core_memory.call_count == 2
        mock_service.add_core_memory.assert_called_with(content="Merged Content")

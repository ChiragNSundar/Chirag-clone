"""
Tests for Cognitive Services (Memory, Notion, Briefing).
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# ============= Daily Briefing Tests =============

@patch('services.calendar_service.get_calendar_service')
@patch('services.daily_briefing_service.get_personality_service')
def test_daily_briefing_generation(mock_get_personality, mock_get_calendar):
    """Test generating briefing text."""
    from services.daily_briefing_service import DailyBriefingService
    
    # Mock Personality
    mock_profile = Mock()
    mock_profile.name = "Chirag"
    mock_personality = Mock()
    mock_personality.get_profile.return_value = mock_profile
    mock_get_personality.return_value = mock_personality
    
    # Mock Calendar
    mock_calendar = Mock()
    mock_calendar.service = True
    mock_calendar.get_upcoming_events.return_value = [
        {'summary': 'Meeting', 'start': '2026-01-21T10:00:00Z'}
    ]
    mock_get_calendar.return_value = mock_calendar
    
    service = DailyBriefingService()
    briefing = service.generate_briefing_text()
    
    assert "Good" in briefing['text']
    assert "Meeting" in briefing['text']
    assert briefing['sections']['calendar'] is True


# ============= Notion Sync Tests =============

def test_notion_text_extraction():
    """Test extracting text from Notion blocks."""
    from services.notion_sync_service import NotionSyncService
    
    service = NotionSyncService()
    
    # Text block
    block = {
        'type': 'paragraph',
        'paragraph': {
            'rich_text': [{'plain_text': 'Hello World'}]
        }
    }
    assert service._extract_text_from_block(block) == 'Hello World'
    
    # To-do block
    todo_block = {
        'type': 'to_do',
        'to_do': {
            'checked': True,
            'rich_text': [{'plain_text': 'Task 1'}]
        }
    }
    assert service._extract_text_from_block(todo_block) == '✓ Task 1'


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

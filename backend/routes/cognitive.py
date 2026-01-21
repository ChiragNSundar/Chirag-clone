"""
Cognitive Routes - Core memory, active learning, and memory summarization endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cognitive", tags=["cognitive"])


# ============= Request Models =============

class ActiveLearningAnswer(BaseModel):
    question: str
    answer: str
    domain: str = ""


# ============= Helper Functions =============

def _get_core_memory_service():
    from services.core_memory_service import get_core_memory_service
    return get_core_memory_service()


# ============= Core Memories =============

@router.get("/core-memories")
async def get_core_memories(category: Optional[str] = None, limit: int = 50):
    """Get all stored core memories."""
    try:
        service = _get_core_memory_service()
        memories = service.get_core_memories(category=category, limit=limit)
        stats = service.get_stats()
        return {"memories": memories, "stats": stats}
    except Exception as e:
        logger.error(f"Core memories error: {e}")
        return {"memories": [], "stats": {}}


@router.delete("/core-memories/{memory_id}")
async def delete_core_memory(memory_id: str):
    """Delete a core memory by ID."""
    try:
        service = _get_core_memory_service()
        success = service.delete_core_memory(memory_id)
        return {"success": success}
    except Exception as e:
        logger.error(f"Delete core memory error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/trigger-summarization")
async def trigger_memory_summarization(days_back: int = 1):
    """Manually trigger memory summarization."""
    try:
        service = _get_core_memory_service()
        
        # Run in threadpool to avoid blocking
        new_memories = await asyncio.to_thread(
            service.summarize_recent_conversations,
            days_back=days_back
        )
        
        return {
            "success": True,
            "new_memories": len(new_memories),
            "memories": new_memories
        }
    except Exception as e:
        logger.error(f"Memory summarization error: {e}")
        return {"success": False, "error": str(e)}


# ============= Active Learning =============

@router.get("/active-learning/suggestions")
async def get_active_learning_suggestions(max_questions: int = 3):
    """Get proactive questions to fill knowledge gaps."""
    try:
        from services.active_learning_service import get_active_learning_service
        service = get_active_learning_service()
        questions = service.get_suggestions(max_questions=max_questions)
        return {"questions": questions}
    except Exception as e:
        logger.error(f"Active learning suggestions error: {e}")
        return {"questions": []}


@router.post("/active-learning/answer")
async def submit_active_learning_answer(data: ActiveLearningAnswer):
    """Submit an answer to a proactive question."""
    try:
        from services.active_learning_service import get_active_learning_service
        from services.memory_service import get_memory_service
        
        al_service = get_active_learning_service()
        memory = get_memory_service()
        
        # Store the answer
        al_service.record_answer(data.question, data.answer, domain=data.domain)
        memory.add_training_example(data.question, data.answer, source="active_learning")
        
        return {"success": True, "message": "Answer recorded"}
    except Exception as e:
        logger.error(f"Active learning answer error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/learning-stats")
async def get_cognitive_learning_stats():
    """Get comprehensive learning statistics."""
    try:
        from services.core_memory_service import get_core_memory_service
        from services.memory_service import get_memory_service
        
        core_memory = get_core_memory_service()
        memory = get_memory_service()
        
        return {
            "core_memory_stats": core_memory.get_stats(),
            "training_stats": memory.get_training_stats()
        }
    except Exception as e:
        logger.error(f"Learning stats error: {e}")
        return {"core_memory_stats": {}, "training_stats": {}}


# ============= Memory Editing =============

class MemoryEditRequest(BaseModel):
    content: str
    category: Optional[str] = None


class MemoryMergeRequest(BaseModel):
    memory_ids: list[str]
    merged_content: str


@router.get("/memories")
async def list_memories(category: Optional[str] = None, limit: int = 100):
    """List core memories with IDs for editing."""
    try:
        service = _get_core_memory_service()
        memories = service.get_core_memories(category=category, limit=limit)
        return {"memories": memories, "total": len(memories)}
    except Exception as e:
        logger.error(f"List memories error: {e}")
        return {"memories": [], "total": 0}


@router.patch("/memories/{memory_id}")
async def edit_memory(memory_id: str, data: MemoryEditRequest):
    """Edit a memory's content."""
    try:
        service = _get_core_memory_service()
        success = service.update_core_memory(
            memory_id=memory_id,
            content=data.content,
            category=data.category
        )
        return {"success": success}
    except Exception as e:
        logger.error(f"Edit memory error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/memories/merge")
async def merge_memories(data: MemoryMergeRequest):
    """Merge two or more memories into one."""
    try:
        service = _get_core_memory_service()
        # Delete old memories
        for mem_id in data.memory_ids:
            service.delete_core_memory(mem_id)
        # Add merged
        new_memory = service.add_core_memory(content=data.merged_content)
        return {"success": True, "new_memory": new_memory}
    except Exception as e:
        logger.error(f"Merge memories error: {e}")
        return {"success": False, "error": str(e)}


# ============= Daily Briefing =============

@router.get("/briefing/today")
async def get_today_briefing(audio: bool = False):
    """Get today's daily briefing."""
    try:
        from services.daily_briefing_service import get_briefing_service
        briefing = get_briefing_service()
        return briefing.get_briefing(audio=audio)
    except Exception as e:
        logger.error(f"Briefing error: {e}")
        return {"text": "Could not generate briefing", "error": str(e)}


# ============= Notion Sync =============

@router.get("/notion/status")
async def get_notion_status():
    """Get Notion sync service status."""
    try:
        from services.notion_sync_service import get_notion_service
        return get_notion_service().get_status()
    except Exception as e:
        logger.error(f"Notion status error: {e}")
        return {"configured": False, "error": str(e)}


@router.post("/notion/sync")
async def trigger_notion_sync():
    """Trigger manual Notion sync."""
    try:
        from services.notion_sync_service import get_notion_service
        notion = get_notion_service()
        result = await asyncio.to_thread(notion.sync_to_knowledge_base)
        return result
    except Exception as e:
        logger.error(f"Notion sync error: {e}")
        return {"success": False, "error": str(e)}


# ============= Wake Word =============

@router.get("/wakeword/status")
async def get_wake_word_status():
    """Get wake word service status."""
    try:
        from services.wake_word_service import get_wake_word_service
        return get_wake_word_service().get_status()
    except Exception as e:
        logger.error(f"Wake word status error: {e}")
        return {"available": False, "error": str(e)}


@router.post("/wakeword/set")
async def set_wake_word(model: str):
    """Change the active wake word model."""
    try:
        from services.wake_word_service import get_wake_word_service
        service = get_wake_word_service()
        success = service.set_wake_word(model)
        return {"success": success, "active_model": service.wake_word}
    except Exception as e:
        logger.error(f"Set wake word error: {e}")
        return {"success": False, "error": str(e)}

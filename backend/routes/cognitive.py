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

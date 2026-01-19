"""
Features Routes - Creative studio, personality history, calendar, quiz, research, and rewind endpoints.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Optional, Dict
import logging
import asyncio
import json

logger = logging.getLogger(__name__)

router = APIRouter(tags=["features"])


# ============= Request Models =============

class CreativeRequest(BaseModel):
    content_type: str
    topic: str = ""
    custom_prompt: Optional[str] = None

class QuizAnswers(BaseModel):
    quiz_id: str
    answers: Dict[str, str]

class DeepResearchQuery(BaseModel):
    query: str = Field(..., min_length=5, max_length=500)
    max_depth: int = Field(default=3, ge=1, le=5)

class RewindQuery(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    time_range_minutes: Optional[float] = Field(default=None, ge=0, le=30)


# ============= Creative Studio =============

@router.get("/api/creative/types")
async def get_creative_types():
    """Get available creative content types."""
    try:
        from services.creative_service import get_creative_service
        service = get_creative_service()
        return {"types": service.get_content_types()}
    except Exception as e:
        logger.error(f"Creative types error: {e}")
        return {"types": []}


@router.post("/api/creative/generate")
async def generate_creative_content(request: CreativeRequest):
    """Generate creative content."""
    try:
        from services.creative_service import get_creative_service
        service = get_creative_service()
        result = await asyncio.to_thread(
            service.generate,
            request.content_type,
            topic=request.topic,
            custom_prompt=request.custom_prompt
        )
        return {"success": True, "content": result}
    except Exception as e:
        logger.error(f"Creative generation error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/creative/daily-prompt")
async def get_daily_prompt():
    """Get daily creative writing prompt."""
    try:
        from services.creative_service import get_creative_service
        service = get_creative_service()
        return {"prompt": service.get_daily_prompt()}
    except Exception as e:
        logger.error(f"Daily prompt error: {e}")
        return {"prompt": "Write about something that made you smile today."}


# ============= Personality History =============

@router.post("/api/personality/snapshot")
async def take_personality_snapshot(note: str = ""):
    """Take a snapshot of current personality."""
    try:
        from services.personality_service import get_personality_service
        service = get_personality_service()
        snapshot = service.take_snapshot(note=note)
        return {"success": True, "snapshot": snapshot}
    except Exception as e:
        logger.error(f"Snapshot error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/personality/history")
async def get_personality_history(limit: int = 20):
    """Get personality snapshot history."""
    try:
        from services.personality_service import get_personality_service
        service = get_personality_service()
        return {"history": service.get_history(limit=limit)}
    except Exception as e:
        logger.error(f"History error: {e}")
        return {"history": []}


@router.get("/api/personality/evolution")
async def get_personality_evolution():
    """Get personality evolution trend."""
    try:
        from services.personality_service import get_personality_service
        service = get_personality_service()
        return {"evolution": service.get_evolution()}
    except Exception as e:
        logger.error(f"Evolution error: {e}")
        return {"evolution": {}}


# ============= Calendar =============

@router.get("/api/calendar/status")
async def get_calendar_status():
    """Get calendar service status."""
    try:
        from services.calendar_service import get_calendar_service
        service = get_calendar_service()
        return service.get_status()
    except Exception as e:
        logger.error(f"Calendar status error: {e}")
        return {"configured": False, "error": str(e)}


@router.get("/api/calendar/events")
async def get_calendar_events(days: int = 7):
    """Get upcoming calendar events."""
    try:
        from services.calendar_service import get_calendar_service
        service = get_calendar_service()
        return {"events": service.get_upcoming_events(days=days)}
    except Exception as e:
        logger.error(f"Calendar events error: {e}")
        return {"events": []}


@router.get("/api/calendar/today-summary")
async def get_today_summary():
    """Get AI-generated summary of today's schedule."""
    try:
        from services.calendar_service import get_calendar_service
        service = get_calendar_service()
        summary = await asyncio.to_thread(service.get_today_summary)
        return {"summary": summary}
    except Exception as e:
        logger.error(f"Today summary error: {e}")
        return {"summary": "Unable to retrieve today's schedule."}


# ============= Accuracy Quiz =============

@router.get("/api/accuracy/quiz")
async def generate_accuracy_quiz(num_questions: int = 5):
    """Generate a clone accuracy quiz."""
    try:
        from services.accuracy_service import get_accuracy_service
        service = get_accuracy_service()
        quiz = await asyncio.to_thread(service.generate_quiz, num_questions)
        return {"quiz": quiz}
    except Exception as e:
        logger.error(f"Quiz generation error: {e}")
        return {"quiz": {"questions": []}}


@router.post("/api/accuracy/submit")
async def submit_quiz_answers(request: QuizAnswers):
    """Submit quiz answers and get score."""
    try:
        from services.accuracy_service import get_accuracy_service
        service = get_accuracy_service()
        result = await asyncio.to_thread(service.score_quiz, request.quiz_id, request.answers)
        return result
    except Exception as e:
        logger.error(f"Quiz submit error: {e}")
        return {"score": 0, "error": str(e)}


@router.get("/api/accuracy/stats")
async def get_accuracy_stats():
    """Get accuracy statistics."""
    try:
        from services.accuracy_service import get_accuracy_service
        service = get_accuracy_service()
        return service.get_stats()
    except Exception as e:
        logger.error(f"Accuracy stats error: {e}")
        return {}


# ============= Deep Research =============

@router.post("/api/research/deep")
async def deep_research(data: DeepResearchQuery):
    """
    Perform deep agentic research on a query.
    Recursively searches the web, scrapes pages, and synthesizes an answer with citations.
    """
    try:
        from services.deep_research_service import get_deep_research_service
        service = get_deep_research_service()
        
        result = await asyncio.to_thread(
            service.research,
            data.query,
            max_depth=data.max_depth
        )
        
        return {
            "success": True,
            "answer": result.get("answer", ""),
            "citations": result.get("citations", []),
            "sources_explored": result.get("sources_explored", 0)
        }
    except Exception as e:
        logger.error(f"Deep research error: {e}")
        return {"success": False, "error": str(e)}


@router.websocket("/api/research/stream")
async def deep_research_stream(websocket: WebSocket):
    """
    WebSocket endpoint for streaming deep research progress.
    Send: {"query": "your question", "max_depth": 3}
    Receive: Progress events and final result
    """
    await websocket.accept()
    
    try:
        data = await websocket.receive_json()
        query = data.get("query", "")
        max_depth = data.get("max_depth", 3)
        
        if not query:
            await websocket.send_json({"type": "error", "message": "Query is required"})
            return
        
        from services.deep_research_service import get_deep_research_service
        service = get_deep_research_service()
        
        # Define progress callback
        async def on_progress(event):
            await websocket.send_json({"type": "progress", **event})
        
        # Run research with streaming
        result = await asyncio.to_thread(
            service.research_with_callbacks,
            query,
            max_depth=max_depth,
            on_progress=lambda e: asyncio.create_task(on_progress(e))
        )
        
        await websocket.send_json({
            "type": "complete",
            "answer": result.get("answer", ""),
            "citations": result.get("citations", [])
        })
        
    except WebSocketDisconnect:
        logger.info("Research WebSocket disconnected")
    except Exception as e:
        logger.error(f"Research stream error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass


@router.get("/api/research/status")
async def research_status():
    """Get deep research service status."""
    try:
        from services.deep_research_service import get_deep_research_service
        service = get_deep_research_service()
        return service.get_status()
    except Exception as e:
        logger.error(f"Research status error: {e}")
        return {"available": False, "error": str(e)}


# ============= Desktop Rewind Memory =============

@router.post("/api/rewind/frame")
async def add_rewind_frame(
    image_base64: str = Form(...),
    window_name: str = Form(...),
    mime_type: str = Form(default="image/png")
):
    """
    Add a frame to the rewind buffer.
    Called by the desktop widget during continuous capture.
    """
    try:
        from services.rewind_service import get_rewind_service
        service = get_rewind_service()
        success = service.add_frame(image_base64, window_name, mime_type)
        return {"success": success}
    except Exception as e:
        logger.error(f"Rewind frame error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/api/rewind/query")
async def query_rewind(data: RewindQuery):
    """
    Query the rewind buffer using natural language.
    """
    try:
        from services.rewind_service import get_rewind_service
        service = get_rewind_service()
        
        result = await asyncio.to_thread(
            service.query,
            data.question,
            time_range_minutes=data.time_range_minutes
        )
        
        return {
            "success": True,
            "answer": result.get("answer", ""),
            "relevant_frames": result.get("frames", [])
        }
    except Exception as e:
        logger.error(f"Rewind query error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/rewind/status")
async def get_rewind_status():
    """Get rewind service status."""
    try:
        from services.rewind_service import get_rewind_service
        service = get_rewind_service()
        return service.get_status()
    except Exception as e:
        logger.error(f"Rewind status error: {e}")
        return {"active": False, "buffer_size": 0, "error": str(e)}


@router.get("/api/rewind/timeline")
async def get_rewind_timeline(limit: int = 20):
    """Get timeline of recent frames."""
    try:
        from services.rewind_service import get_rewind_service
        return {"timeline": get_rewind_service().get_timeline(limit)}
    except Exception as e:
        return {"timeline": [], "error": str(e)}


@router.post("/api/rewind/pause")
async def pause_rewind():
    """Pause rewind capture."""
    from services.rewind_service import get_rewind_service
    return get_rewind_service().pause()


@router.post("/api/rewind/resume")
async def resume_rewind():
    """Resume rewind capture."""
    from services.rewind_service import get_rewind_service
    return get_rewind_service().resume()


@router.delete("/api/rewind/clear")
async def clear_rewind():
    """Clear rewind buffer (privacy)."""
    from services.rewind_service import get_rewind_service
    return get_rewind_service().clear()


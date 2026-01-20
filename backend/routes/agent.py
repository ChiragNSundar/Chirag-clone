
"""
Agent Routes - Interfaces for autonomous agent capabilities.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from services.browser_service import get_browser_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

class BrowseRequest(BaseModel):
    url: str
    instruction: Optional[str] = None

@router.post("/browse")
async def browse_web(request: BrowseRequest):
    """
    Agentic Web Browsing: Navigate to a URL and capture content/screenshot.
    """
    service = get_browser_service()
    if not service.enabled:
        raise HTTPException(status_code=503, detail="Browser service unavailable (Playwright not installed)")
    
    try:
        # Simple browse for now, "instruction" could be used for more complex actions later
        result = await service.browse(request.url)
        
        if result.get("status") == "failed":
            raise HTTPException(status_code=500, detail=result.get("error"))
            
        return result
    except Exception as e:
        logger.error(f"Agent browse error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

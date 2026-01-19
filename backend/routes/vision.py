"""
Vision Routes - Desktop screenshot analysis and image analysis endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vision", tags=["vision"])


# ============= Request Models =============

class DesktopVisionRequest(BaseModel):
    image_base64: str
    mime_type: str = "image/png"


# ============= Helper Functions =============

def _get_vision_service():
    from services.vision_service import get_vision_service
    return get_vision_service()


# ============= Vision Analysis Endpoints =============

@router.post("/analyze-desktop")
async def analyze_desktop_screen(request: DesktopVisionRequest):
    """
    Analyze a desktop screenshot for proactive assistance.
    Returns a contextual suggestion based on what the user is viewing.
    """
    try:
        service = _get_vision_service()
        
        # Check if vision is available
        if not service.is_available():
            return {
                "success": False,
                "error": "Vision service not available",
                "suggestion": None
            }
        
        # Analyze the screenshot
        result = await asyncio.to_thread(
            service.analyze_desktop_screenshot,
            request.image_base64,
            request.mime_type
        )
        
        return {
            "success": True,
            "analysis": result.get("analysis", ""),
            "suggestion": result.get("suggestion", ""),
            "detected_context": result.get("context", {}),
            "actions": result.get("actions", [])
        }
    except Exception as e:
        logger.error(f"Desktop vision error: {e}")
        return {
            "success": False,
            "error": str(e),
            "suggestion": None
        }


@router.post("/analyze-image")
async def analyze_image_endpoint(request: DesktopVisionRequest):
    """General image analysis endpoint."""
    try:
        service = _get_vision_service()
        
        if not service.is_available():
            return {
                "success": False,
                "error": "Vision service not available"
            }
        
        result = await asyncio.to_thread(
            service.analyze_image,
            request.image_base64,
            request.mime_type
        )
        
        return {
            "success": True,
            "description": result.get("description", ""),
            "objects": result.get("objects", []),
            "text": result.get("text", "")
        }
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/status")
async def get_vision_status():
    """Get vision service status."""
    try:
        service = _get_vision_service()
        return {
            "available": service.is_available(),
            "provider": service.get_provider()
        }
    except Exception as e:
        logger.error(f"Vision status error: {e}")
        return {"available": False, "error": str(e)}

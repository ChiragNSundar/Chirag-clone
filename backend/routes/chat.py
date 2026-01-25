"""
Chat Routes - Core chat messaging endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator
from typing import Optional
import logging
import asyncio
import re

from config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=Config.MAX_MESSAGE_LENGTH)
    session_id: str = Field(default="default", max_length=100)
    training_mode: bool = False
    image: Optional[str] = None  # Base64 encoded image
    
    @validator('message')
    def sanitize_message(cls, v):
        # Strip leading/trailing whitespace
        v = v.strip()
        if not v:
            raise ValueError('Message cannot be empty')
        return v
    
    @validator('session_id')
    def sanitize_session_id(cls, v):
        # Remove any potentially dangerous characters
        v = re.sub(r'[^a-zA-Z0-9_-]', '', v)
        return v or "default"


def _get_chat_service():
    from services.chat_service import get_chat_service
    return get_chat_service()


@router.post("/message")
async def chat_message(data: ChatMessage):
    """Handle chat messages"""
    try:
        service = _get_chat_service()
        
        # Run synchronous service in threadpool to avoid blocking event loop
        response, confidence, mood_data, thinking_data = await asyncio.to_thread(
            service.generate_response, 
            data.message, 
            data.session_id,
            data.image,  # New Argument
            True,  # include_examples
            data.training_mode
        )
        
        return {
            "response": response,
            "session_id": data.session_id,
            "confidence": confidence,
            "mood": mood_data,
            "thinking": thinking_data
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

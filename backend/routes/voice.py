"""
Voice Routes - Text-to-speech, speech-to-text, and real-time voice streaming.
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import asyncio
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


# ============= Request Models =============

class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None

class STTRequest(BaseModel):
    audio_base64: str
    audio_format: str = "webm"

class RealtimeAudioChunk(BaseModel):
    audio_base64: str
    audio_format: str = "webm"
    session_id: str = "default"

class RealtimeProcessRequest(BaseModel):
    session_id: str = "default"


# ============= Helper Functions =============

def _get_voice_service():
    from services.voice_service import get_voice_service
    return get_voice_service()

def _get_realtime_voice_service():
    from services.realtime_voice_service import get_realtime_voice_service
    return get_realtime_voice_service()


# ============= Basic Voice Endpoints =============

@router.get("/status")
async def get_voice_status():
    """Get voice service status."""
    try:
        service = _get_voice_service()
        return service.get_status()
    except Exception as e:
        logger.error(f"Voice status error: {e}")
        return {"tts_available": False, "stt_available": False, "error": str(e)}


@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech audio."""
    try:
        service = _get_voice_service()
        result = await asyncio.to_thread(
            service.text_to_speech,
            request.text,
            voice_id=request.voice_id
        )
        return result
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stt")
async def speech_to_text(request: STTRequest):
    """Convert speech audio to text."""
    try:
        import base64
        service = _get_voice_service()
        audio_bytes = base64.b64decode(request.audio_base64)
        result = await asyncio.to_thread(
            service.speech_to_text,
            audio_bytes,
            audio_format=request.audio_format
        )
        return result
    except Exception as e:
        logger.error(f"STT error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voices")
async def get_available_voices():
    """Get list of available TTS voices."""
    try:
        service = _get_voice_service()
        voices = service.get_available_voices()
        return {"voices": voices}
    except Exception as e:
        logger.error(f"Get voices error: {e}")
        return {"voices": []}


# ============= Real-Time Voice Streaming =============

@router.websocket("/realtime/stream")
async def realtime_voice_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice streaming.
    
    Protocol:
    - Client sends JSON: {"type": "audio", "audio_base64": "...", "format": "webm"}
    - Client sends JSON: {"type": "end_turn"} when user stops speaking
    - Server sends JSON: {"type": "status", "is_speaking": true/false}
    - Server sends JSON: {"type": "transcript", "text": "..."}
    - Server sends JSON: {"type": "response", "text": "...", "audio_base64": "...", "format": "mp3"}
    """
    await websocket.accept()
    
    session_id = None
    realtime_service = _get_realtime_voice_service()
    
    try:
        # Initial handshake
        init_data = await websocket.receive_json()
        session_id = init_data.get("session_id", "ws_" + str(id(websocket)))
        
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Real-time voice session started"
        })
        
        # Background task for silence detection
        async def silence_checker():
            while True:
                await asyncio.sleep(0.5)  # Check every 500ms
                result = await realtime_service.check_silence_and_process(session_id)
                if result and result.get("status") == "success":
                    await websocket.send_json({
                        "type": "response",
                        "text": result.get("response_text", ""),
                        "audio_base64": result.get("response_audio"),
                        "format": result.get("audio_format", "mp3"),
                        "transcript": result.get("transcript", ""),
                        "confidence": result.get("confidence", 0),
                        "mood": result.get("mood")
                    })
        
        silence_task = asyncio.create_task(silence_checker())
        
        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")
                
                if msg_type == "audio":
                    # Handle audio chunk
                    result = await realtime_service.handle_audio_chunk(
                        session_id,
                        data.get("audio_base64", ""),
                        data.get("format", "webm")
                    )
                    
                    if result.get("status") == "interrupted":
                        await websocket.send_json({
                            "type": "interrupted",
                            "message": "Bot speech interrupted"
                        })
                    
                elif msg_type == "end_turn":
                    # User explicitly ended their turn
                    result = await realtime_service.process_buffered_audio(session_id)
                    
                    if result.get("status") == "success":
                        await websocket.send_json({
                            "type": "transcript",
                            "text": result.get("transcript", "")
                        })
                        await websocket.send_json({
                            "type": "response",
                            "text": result.get("response_text", ""),
                            "audio_base64": result.get("response_audio"),
                            "format": result.get("audio_format", "mp3"),
                            "confidence": result.get("confidence", 0),
                            "mood": result.get("mood")
                        })
                    elif result.get("status") == "empty":
                        await websocket.send_json({
                            "type": "status",
                            "message": "No speech detected"
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": result.get("message", "Processing failed")
                        })
                        
                elif msg_type == "speech_complete":
                    # Bot finished speaking
                    realtime_service.mark_bot_speech_complete(session_id)
                    
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        finally:
            silence_task.cancel()
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        if session_id:
            realtime_service.end_session(session_id)


# ============= HTTP Fallback Endpoints =============

@router.post("/realtime/chunk")
async def handle_realtime_audio_chunk(request: RealtimeAudioChunk):
    """HTTP fallback for sending audio chunks (for browsers without WebSocket)."""
    try:
        service = _get_realtime_voice_service()
        result = await service.handle_audio_chunk(
            request.session_id,
            request.audio_base64,
            request.audio_format
        )
        return result
    except Exception as e:
        logger.error(f"Realtime chunk error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/realtime/process")
async def process_realtime_audio(request: RealtimeProcessRequest):
    """HTTP fallback for processing buffered audio."""
    try:
        service = _get_realtime_voice_service()
        result = await service.process_buffered_audio(request.session_id)
        return result
    except Exception as e:
        logger.error(f"Realtime process error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/realtime/status/{session_id}")
async def get_realtime_session_status(session_id: str):
    """Get status of a real-time voice session."""
    try:
        service = _get_realtime_voice_service()
        return service.get_session_status(session_id)
    except Exception as e:
        logger.error(f"Realtime status error: {e}")
        return {"error": str(e)}

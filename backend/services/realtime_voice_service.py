"""
Real-Time Voice Service - WebSocket-based bidirectional audio streaming.
Enables natural, interruptible voice conversations with the digital twin.
"""
import asyncio
import base64
import json
from datetime import datetime
from typing import Optional, Dict, Callable, Any
from dataclasses import dataclass, field

from .logger import get_logger
from .voice_service import get_voice_service
from .chat_service import get_chat_service

logger = get_logger(__name__)


@dataclass
class ConversationState:
    """Tracks the state of a real-time voice conversation."""
    session_id: str
    is_user_speaking: bool = False
    is_bot_speaking: bool = False
    last_user_audio_time: float = 0.0
    audio_buffer: bytes = field(default_factory=bytes)
    pending_response: Optional[str] = None
    interrupted: bool = False


class RealtimeVoiceService:
    """
    Service for real-time voice conversations using WebSocket.
    
    Features:
    - Bidirectional audio streaming
    - Turn-taking with interruption detection
    - Automatic silence detection
    - Integration with existing VoiceService for TTS/STT
    """
    
    # Configuration
    SILENCE_THRESHOLD_MS = 1500  # Silence duration to trigger processing
    MAX_AUDIO_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB max buffer
    
    def __init__(self):
        self.voice_service = get_voice_service()
        self.active_sessions: Dict[str, ConversationState] = {}
    
    def get_session(self, session_id: str) -> ConversationState:
        """Get or create a conversation session."""
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = ConversationState(session_id=session_id)
        return self.active_sessions[session_id]
    
    def end_session(self, session_id: str):
        """End a conversation session."""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
    
    async def handle_audio_chunk(
        self,
        session_id: str,
        audio_base64: str,
        audio_format: str = "webm"
    ) -> Dict[str, Any]:
        """
        Handle an incoming audio chunk from the client.
        
        Args:
            session_id: Unique session identifier
            audio_base64: Base64 encoded audio chunk
            audio_format: Audio format (webm, wav, etc.)
            
        Returns:
            Dict with processing status and any response data
        """
        session = self.get_session(session_id)
        
        try:
            # Decode audio
            audio_bytes = base64.b64decode(audio_base64)
            
            # Check buffer size limit
            if len(session.audio_buffer) + len(audio_bytes) > self.MAX_AUDIO_BUFFER_SIZE:
                logger.warning(f"Audio buffer overflow for session {session_id}")
                session.audio_buffer = bytes()  # Reset buffer
                return {"status": "error", "message": "Audio buffer overflow"}
            
            # Append to buffer
            session.audio_buffer += audio_bytes
            session.last_user_audio_time = asyncio.get_event_loop().time()
            session.is_user_speaking = True
            
            # If bot was speaking, mark as interrupted
            if session.is_bot_speaking:
                session.interrupted = True
                session.is_bot_speaking = False
                return {
                    "status": "interrupted",
                    "message": "Bot speech interrupted by user"
                }
            
            return {"status": "buffering", "buffer_size": len(session.audio_buffer)}
            
        except Exception as e:
            logger.error(f"Error handling audio chunk: {e}")
            return {"status": "error", "message": str(e)}
    
    async def process_buffered_audio(
        self,
        session_id: str,
        on_transcript: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Process buffered audio when silence is detected.
        
        Args:
            session_id: Session identifier
            on_transcript: Optional callback for transcript
            
        Returns:
            Dict with transcript and response
        """
        session = self.get_session(session_id)
        
        if not session.audio_buffer:
            return {"status": "empty", "message": "No audio to process"}
        
        try:
            # Transcribe audio
            stt_result = self.voice_service.speech_to_text(
                session.audio_buffer,
                audio_format="webm"
            )
            
            # Clear buffer
            session.audio_buffer = bytes()
            session.is_user_speaking = False
            
            if not stt_result or "error" in stt_result:
                return {
                    "status": "error",
                    "message": stt_result.get("error", "STT failed")
                }
            
            transcript = stt_result.get("text", "")
            
            if not transcript.strip():
                return {"status": "empty", "message": "No speech detected"}
            
            # Notify callback if provided
            if on_transcript:
                on_transcript(transcript)
            
            # Generate response using chat service
            chat_service = get_chat_service()
            response_text, confidence, mood = chat_service.generate_response(
                transcript,
                session_id=session_id
            )
            
            session.pending_response = response_text
            
            # Generate TTS for response
            tts_result = self.voice_service.text_to_speech(response_text)
            
            if tts_result and "audio_base64" in tts_result:
                session.is_bot_speaking = True
                return {
                    "status": "success",
                    "transcript": transcript,
                    "response_text": response_text,
                    "response_audio": tts_result["audio_base64"],
                    "audio_format": "mp3",
                    "confidence": confidence,
                    "mood": mood
                }
            else:
                # Return text-only response if TTS fails
                return {
                    "status": "success",
                    "transcript": transcript,
                    "response_text": response_text,
                    "response_audio": None,
                    "confidence": confidence,
                    "mood": mood
                }
                
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            session.audio_buffer = bytes()
            return {"status": "error", "message": str(e)}
    
    async def check_silence_and_process(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if silence threshold has been reached and process if so.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Processing result if silence detected, None otherwise
        """
        session = self.get_session(session_id)
        
        if not session.is_user_speaking or not session.audio_buffer:
            return None
        
        current_time = asyncio.get_event_loop().time()
        silence_duration = (current_time - session.last_user_audio_time) * 1000  # to ms
        
        if silence_duration >= self.SILENCE_THRESHOLD_MS:
            return await self.process_buffered_audio(session_id)
        
        return None
    
    def mark_bot_speech_complete(self, session_id: str):
        """Mark that the bot has finished speaking."""
        session = self.get_session(session_id)
        session.is_bot_speaking = False
        session.interrupted = False
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get the current status of a session."""
        session = self.get_session(session_id)
        return {
            "session_id": session_id,
            "is_user_speaking": session.is_user_speaking,
            "is_bot_speaking": session.is_bot_speaking,
            "buffer_size": len(session.audio_buffer),
            "interrupted": session.interrupted,
            "has_pending_response": session.pending_response is not None
        }


# Singleton instance
_realtime_voice_service: Optional[RealtimeVoiceService] = None


def get_realtime_voice_service() -> RealtimeVoiceService:
    """Get the singleton realtime voice service instance."""
    global _realtime_voice_service
    if _realtime_voice_service is None:
        _realtime_voice_service = RealtimeVoiceService()
    return _realtime_voice_service

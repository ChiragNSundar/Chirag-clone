"""
Real-Time Voice Service - WebSocket-based bidirectional audio streaming.
Enables natural, interruptible voice conversations with the digital twin.
"""
import asyncio
import base64
import json
import struct
from datetime import datetime
from typing import Optional, Dict, Callable, Any, List
from dataclasses import dataclass, field
from enum import Enum

from .logger import get_logger
from .voice_service import get_voice_service
from .chat_service import get_chat_service

logger = get_logger(__name__)

# Try to import webrtcvad for Voice Activity Detection
try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    logger.warning("webrtcvad not installed. Using energy-based VAD fallback.")


class VoiceState(Enum):
    """States for the voice conversation."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


@dataclass
class ConversationState:
    """Tracks the state of a real-time voice conversation."""
    session_id: str
    state: VoiceState = VoiceState.IDLE
    is_user_speaking: bool = False
    is_bot_speaking: bool = False
    last_user_audio_time: float = 0.0
    audio_buffer: bytes = field(default_factory=bytes)
    pending_response: Optional[str] = None
    interrupted: bool = False
    # VAD tracking
    vad_frames: List[bool] = field(default_factory=list)
    consecutive_speech_frames: int = 0
    consecutive_silence_frames: int = 0
    # Audio playback tracking for barge-in
    current_audio_id: Optional[str] = None
    audio_position_ms: int = 0


class RealtimeVoiceService:
    """
    Service for real-time voice conversations using WebSocket.
    
    Features:
    - Bidirectional audio streaming
    - VAD-based turn-taking with interruption detection
    - Automatic silence detection
    - Barge-in capability (interrupt bot mid-speech)
    - Integration with existing VoiceService for TTS/STT
    """
    
    # Configuration
    SILENCE_THRESHOLD_MS = 1500  # Silence duration to trigger processing
    MAX_AUDIO_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB max buffer
    
    # VAD Configuration
    VAD_AGGRESSIVENESS = 2  # 0-3, higher = more aggressive filtering
    VAD_FRAME_DURATION_MS = 30  # 10, 20, or 30 ms
    SPEECH_FRAMES_THRESHOLD = 3  # Consecutive speech frames to confirm speaking
    SILENCE_FRAMES_THRESHOLD = 10  # Consecutive silence frames to confirm silence
    
    # Barge-in Configuration
    BARGE_IN_ENABLED = True
    MIN_BARGE_IN_ENERGY = 500  # Minimum audio energy to trigger barge-in
    
    def __init__(self):
        self.voice_service = get_voice_service()
        self.active_sessions: Dict[str, ConversationState] = {}
        
        # Initialize VAD if available
        if VAD_AVAILABLE:
            self.vad = webrtcvad.Vad(self.VAD_AGGRESSIVENESS)
        else:
            self.vad = None
    
    def _detect_voice_activity_energy(self, audio_bytes: bytes) -> bool:
        """
        Fallback VAD using simple energy detection.
        
        Args:
            audio_bytes: Raw audio bytes
            
        Returns:
            True if voice activity detected
        """
        if len(audio_bytes) < 2:
            return False
        
        # Calculate RMS energy
        try:
            samples = struct.unpack(f'{len(audio_bytes)//2}h', audio_bytes)
            rms = (sum(s**2 for s in samples) / len(samples)) ** 0.5
            return rms > self.MIN_BARGE_IN_ENERGY
        except struct.error:
            return False
    
    def detect_voice_activity(self, audio_bytes: bytes, sample_rate: int = 16000) -> bool:
        """
        Detect voice activity in audio chunk using WebRTC VAD or energy fallback.
        
        Args:
            audio_bytes: Raw PCM audio bytes (16-bit, mono)
            sample_rate: Audio sample rate (8000, 16000, 32000, or 48000)
            
        Returns:
            True if voice activity detected
        """
        if self.vad is not None:
            try:
                # WebRTC VAD requires specific frame sizes
                frame_size = int(sample_rate * self.VAD_FRAME_DURATION_MS / 1000) * 2
                if len(audio_bytes) >= frame_size:
                    return self.vad.is_speech(audio_bytes[:frame_size], sample_rate)
            except Exception as e:
                logger.warning(f"VAD error, using fallback: {e}")
        
        return self._detect_voice_activity_energy(audio_bytes)
    
    def handle_barge_in(self, session_id: str) -> Dict[str, Any]:
        """
        Handle user interrupting bot speech (barge-in).
        
        Args:
            session_id: Session to interrupt
            
        Returns:
            Status dict with interrupt confirmation
        """
        session = self.get_session(session_id)
        
        if session.is_bot_speaking:
            session.interrupted = True
            session.is_bot_speaking = False
            session.state = VoiceState.INTERRUPTED
            session.current_audio_id = None
            
            logger.info(f"Barge-in triggered for session {session_id}")
            
            return {
                "status": "interrupted",
                "type": "barge_in",
                "message": "Bot speech interrupted by user",
                "audio_position_ms": session.audio_position_ms
            }
        
        return {"status": "no_action", "message": "Bot was not speaking"}
    
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

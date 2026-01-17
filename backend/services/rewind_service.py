"""
Rewind Service - Temporal memory buffer for desktop screen capture.
Enables answering questions like "What was I looking at 10 minutes ago?"
"""
import base64
import io
import time
import hashlib
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from threading import Lock

from services.logger import get_logger
from services.vision_service import get_vision_service
from config import Config

logger = get_logger(__name__)

# Try to import Pillow for image compression
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("Pillow not installed. Rewind will use uncompressed images.")


@dataclass
class RewindFrame:
    """A single captured frame with metadata."""
    timestamp: datetime
    window_name: str
    image_base64: str  # Compressed JPEG base64
    image_hash: str    # For deduplication
    analyzed: bool = False
    analysis_text: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'window_name': self.window_name,
            'image_preview': self.image_base64[:100] + '...' if len(self.image_base64) > 100 else self.image_base64,
            'analyzed': self.analyzed,
            'analysis': self.analysis_text
        }
    
    def age_minutes(self) -> float:
        """Get age of frame in minutes."""
        return (datetime.now() - self.timestamp).total_seconds() / 60


class RewindService:
    """
    Service for managing a rolling buffer of screen captures.
    Provides temporal queries like "What was I looking at N minutes ago?"
    """
    
    # Configuration
    MAX_BUFFER_MINUTES = 30  # Keep last 30 minutes
    CAPTURE_INTERVAL_SECONDS = 5  # 1 frame every 5 seconds
    MAX_IMAGE_SIZE = (640, 360)  # Resize for storage efficiency
    JPEG_QUALITY = 60  # Compression quality (0-100)
    
    # Calculated: ~360 frames for 30 mins at 5s interval = ~18MB at ~50KB/frame
    MAX_FRAMES = (MAX_BUFFER_MINUTES * 60) // CAPTURE_INTERVAL_SECONDS
    
    def __init__(self):
        self._buffer: deque[RewindFrame] = deque(maxlen=self.MAX_FRAMES)
        self._lock = Lock()
        self._paused = False
        self._excluded_windows: set = {'Terminal', 'Activity Monitor', 'Keychain Access'}
        self._vision_service = get_vision_service()
        self._last_hash: Optional[str] = None
        
        logger.info(f"Rewind service initialized: {self.MAX_FRAMES} frame buffer ({self.MAX_BUFFER_MINUTES} mins)")
    
    # ============= Frame Management =============
    
    def add_frame(
        self,
        image_base64: str,
        window_name: str,
        mime_type: str = "image/png"
    ) -> Dict:
        """
        Add a new frame to the rewind buffer.
        
        Args:
            image_base64: Base64-encoded screenshot
            window_name: Name of the active window
            mime_type: Image MIME type
            
        Returns:
            Dict with success status and frame info
        """
        if self._paused:
            return {'success': False, 'reason': 'paused'}
        
        # Check excluded windows
        if any(exc.lower() in window_name.lower() for exc in self._excluded_windows):
            return {'success': False, 'reason': 'excluded_window'}
        
        try:
            # Compute hash for deduplication
            image_hash = hashlib.md5(image_base64[:1000].encode()).hexdigest()
            
            # Skip if same as last frame
            if image_hash == self._last_hash:
                return {'success': False, 'reason': 'duplicate'}
            
            self._last_hash = image_hash
            
            # Compress image for storage
            compressed_b64 = self._compress_image(image_base64, mime_type)
            
            frame = RewindFrame(
                timestamp=datetime.now(),
                window_name=window_name,
                image_base64=compressed_b64,
                image_hash=image_hash
            )
            
            with self._lock:
                self._buffer.append(frame)
            
            return {
                'success': True,
                'frame_count': len(self._buffer),
                'timestamp': frame.timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to add rewind frame: {e}")
            return {'success': False, 'error': str(e)}
    
    def _compress_image(self, image_base64: str, mime_type: str) -> str:
        """Compress and resize image for efficient storage."""
        if not HAS_PIL:
            return image_base64  # Return as-is if no Pillow
        
        try:
            # Decode
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data))
            
            # Resize if larger than max size
            if image.size[0] > self.MAX_IMAGE_SIZE[0] or image.size[1] > self.MAX_IMAGE_SIZE[1]:
                image.thumbnail(self.MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary (for JPEG)
            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')
            
            # Compress to JPEG
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=self.JPEG_QUALITY, optimize=True)
            buffer.seek(0)
            
            return base64.b64encode(buffer.read()).decode('utf-8')
            
        except Exception as e:
            logger.warning(f"Image compression failed: {e}")
            return image_base64
    
    # ============= Temporal Queries =============
    
    def get_frame_at_time(self, minutes_ago: float) -> Optional[RewindFrame]:
        """
        Get the frame closest to N minutes ago.
        
        Args:
            minutes_ago: How many minutes in the past
            
        Returns:
            RewindFrame or None
        """
        target_time = datetime.now() - timedelta(minutes=minutes_ago)
        
        with self._lock:
            if not self._buffer:
                return None
            
            # Find closest frame
            closest = None
            min_diff = float('inf')
            
            for frame in self._buffer:
                diff = abs((frame.timestamp - target_time).total_seconds())
                if diff < min_diff:
                    min_diff = diff
                    closest = frame
            
            return closest
    
    def query(
        self,
        question: str,
        time_range_minutes: Optional[float] = None
    ) -> Dict:
        """
        Answer a question about what was on screen.
        
        Args:
            question: Natural language question (e.g., "What was I reading?")
            time_range_minutes: Optional specific time (e.g., 10 = "10 mins ago")
            
        Returns:
            Dict with answer and relevant frames
        """
        with self._lock:
            frames = list(self._buffer)
        
        if not frames:
            return {
                'success': False,
                'error': 'No frames in buffer. Enable Rewind and wait a few seconds.'
            }
        
        # If specific time requested, get that frame
        if time_range_minutes is not None:
            target_frame = self.get_frame_at_time(time_range_minutes)
            if target_frame:
                frames = [target_frame]
            else:
                return {
                    'success': False,
                    'error': f'No frame available from {time_range_minutes} minutes ago'
                }
        else:
            # Get recent frames for context (last 5)
            frames = frames[-5:]
        
        # Analyze frames if not already done
        analyzed_frames = []
        for frame in frames:
            if not frame.analyzed:
                analysis = self._analyze_frame(frame)
                frame.analyzed = True
                frame.analysis_text = analysis
            analyzed_frames.append(frame)
        
        # Build context for LLM
        context = self._build_context(analyzed_frames, question)
        answer = self._generate_answer(question, context)
        
        return {
            'success': True,
            'answer': answer,
            'frames_analyzed': len(analyzed_frames),
            'time_range': {
                'oldest': frames[0].timestamp.isoformat() if frames else None,
                'newest': frames[-1].timestamp.isoformat() if frames else None
            }
        }
    
    def _analyze_frame(self, frame: RewindFrame) -> str:
        """Analyze a frame using vision service."""
        try:
            result = self._vision_service.analyze_image(
                frame.image_base64,
                prompt="Describe what's on this computer screen in 2-3 sentences. Focus on the main content (documents, websites, apps) and any visible text.",
                mime_type="image/jpeg"
            )
            if result.get('success'):
                return result.get('description', '')
            return f"[Could not analyze: {result.get('error', 'unknown')}]"
        except Exception as e:
            return f"[Analysis failed: {e}]"
    
    def _build_context(self, frames: List[RewindFrame], question: str) -> str:
        """Build context from analyzed frames."""
        context = "SCREEN HISTORY:\n"
        for frame in frames:
            age = frame.age_minutes()
            context += f"\n[{age:.1f} minutes ago - {frame.window_name}]\n"
            context += f"{frame.analysis_text or 'No analysis'}\n"
        return context
    
    def _generate_answer(self, question: str, context: str) -> str:
        """Generate answer using LLM."""
        try:
            from services.llm_service import get_llm_service
            llm = get_llm_service()
            
            prompt = f"""You are a helpful assistant answering questions about what the user was looking at on their computer.

{context}

USER QUESTION: {question}

Answer the question based on the screen history above. Be specific and helpful. If you can't answer, explain what information you do have."""

            return llm.generate_response(
                system_prompt="You are a helpful assistant with access to the user's recent screen history.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=500
            )
        except Exception as e:
            logger.error(f"Rewind answer generation failed: {e}")
            return f"Sorry, I couldn't generate an answer: {e}"
    
    # ============= Controls =============
    
    def pause(self):
        """Pause frame capture."""
        self._paused = True
        logger.info("Rewind paused")
        return {'success': True, 'paused': True}
    
    def resume(self):
        """Resume frame capture."""
        self._paused = False
        logger.info("Rewind resumed")
        return {'success': True, 'paused': False}
    
    def clear(self):
        """Clear the buffer (privacy)."""
        with self._lock:
            count = len(self._buffer)
            self._buffer.clear()
            self._last_hash = None
        logger.info(f"Rewind cleared: {count} frames deleted")
        return {'success': True, 'frames_cleared': count}
    
    def add_excluded_window(self, window_name: str):
        """Add a window to the exclusion list."""
        self._excluded_windows.add(window_name)
        return {'success': True, 'excluded': list(self._excluded_windows)}
    
    def remove_excluded_window(self, window_name: str):
        """Remove a window from the exclusion list."""
        self._excluded_windows.discard(window_name)
        return {'success': True, 'excluded': list(self._excluded_windows)}
    
    def get_status(self) -> Dict:
        """Get service status."""
        with self._lock:
            buffer_size = len(self._buffer)
            oldest = self._buffer[0].timestamp if self._buffer else None
            newest = self._buffer[-1].timestamp if self._buffer else None
        
        return {
            'enabled': not self._paused,
            'paused': self._paused,
            'frame_count': buffer_size,
            'max_frames': self.MAX_FRAMES,
            'buffer_minutes': self.MAX_BUFFER_MINUTES,
            'capture_interval': self.CAPTURE_INTERVAL_SECONDS,
            'oldest_frame': oldest.isoformat() if oldest else None,
            'newest_frame': newest.isoformat() if newest else None,
            'excluded_windows': list(self._excluded_windows)
        }
    
    def get_timeline(self, limit: int = 20) -> List[Dict]:
        """Get a timeline of recent frames for UI display."""
        with self._lock:
            frames = list(self._buffer)[-limit:]
        
        return [
            {
                'timestamp': f.timestamp.isoformat(),
                'age_minutes': f.age_minutes(),
                'window_name': f.window_name,
                'analyzed': f.analyzed,
                'preview': f.image_base64[:200] + '...' if len(f.image_base64) > 200 else f.image_base64
            }
            for f in reversed(frames)  # Most recent first
        ]


# ============= Singleton =============

_rewind_service: Optional[RewindService] = None


def get_rewind_service() -> RewindService:
    """Get the singleton rewind service instance."""
    global _rewind_service
    if _rewind_service is None:
        _rewind_service = RewindService()
    return _rewind_service

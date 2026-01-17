"""
Tests for Rewind Service (Desktop Temporal Memory)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import base64


class TestRewindFrame:
    """Tests for RewindFrame dataclass."""
    
    def test_frame_creation(self):
        """Test creating a rewind frame."""
        from services.rewind_service import RewindFrame
        
        frame = RewindFrame(
            timestamp=datetime.now(),
            window_name="Test Window",
            image_base64="dGVzdA==",  # base64 of "test"
            image_hash="abc123"
        )
        
        assert frame.window_name == "Test Window"
        assert frame.analyzed is False
        assert frame.analysis_text is None
    
    def test_frame_age_minutes(self):
        """Test age calculation."""
        from services.rewind_service import RewindFrame
        
        # Frame from 5 minutes ago
        past_time = datetime.now() - timedelta(minutes=5)
        frame = RewindFrame(
            timestamp=past_time,
            window_name="Test",
            image_base64="dGVzdA==",
            image_hash="abc123"
        )
        
        age = frame.age_minutes()
        assert 4.9 < age < 5.1  # Allow small tolerance
    
    def test_frame_to_dict(self):
        """Test serialization."""
        from services.rewind_service import RewindFrame
        
        frame = RewindFrame(
            timestamp=datetime.now(),
            window_name="Chrome",
            image_base64="dGVzdA==",
            image_hash="abc123",
            analyzed=True,
            analysis_text="User was browsing docs"
        )
        
        d = frame.to_dict()
        assert 'timestamp' in d
        assert 'window_name' in d
        assert d['analyzed'] is True
        assert d['analysis'] == "User was browsing docs"


class TestRewindService:
    """Tests for RewindService class."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh rewind service for each test."""
        from services.rewind_service import RewindService
        return RewindService()
    
    def test_init(self, service):
        """Test service initialization."""
        assert service.MAX_BUFFER_MINUTES == 30
        assert service.CAPTURE_INTERVAL_SECONDS == 5
        assert not service._paused
    
    def test_add_frame_basic(self, service):
        """Test adding a basic frame."""
        # Simple base64 image (1x1 pixel PNG)
        test_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        with patch.object(service, '_compress_image', return_value=test_image):
            result = service.add_frame(test_image, "Test Window")
        
        assert result['success'] is True
        assert result['frame_count'] == 1
    
    def test_add_frame_when_paused(self, service):
        """Test that frames are rejected when paused."""
        service.pause()
        
        result = service.add_frame("test_image", "Test Window")
        
        assert result['success'] is False
        assert result['reason'] == 'paused'
    
    def test_add_frame_excluded_window(self, service):
        """Test that excluded windows are skipped."""
        result = service.add_frame("test_image", "Terminal")
        
        assert result['success'] is False
        assert result['reason'] == 'excluded_window'
    
    def test_add_frame_duplicate(self, service):
        """Test that duplicate frames are skipped."""
        test_image = "same_image_content_here"
        
        with patch.object(service, '_compress_image', return_value=test_image):
            result1 = service.add_frame(test_image, "Window 1")
            result2 = service.add_frame(test_image, "Window 1")  # Same image
        
        assert result1['success'] is True
        assert result2['success'] is False
        assert result2['reason'] == 'duplicate'
    
    def test_pause_resume(self, service):
        """Test pause and resume functionality."""
        assert not service._paused
        
        service.pause()
        assert service._paused
        
        service.resume()
        assert not service._paused
    
    def test_clear(self, service):
        """Test clearing the buffer."""
        # Add some frames first
        with patch.object(service, '_compress_image', return_value="test"):
            service.add_frame("img1", "Window 1")
            service._last_hash = None  # Reset for next frame
            service.add_frame("img2", "Window 2")
        
        result = service.clear()
        
        assert result['success'] is True
        assert result['frames_cleared'] >= 0
        assert len(service._buffer) == 0
    
    def test_get_status(self, service):
        """Test status retrieval."""
        status = service.get_status()
        
        assert 'enabled' in status
        assert 'paused' in status
        assert 'frame_count' in status
        assert 'max_frames' in status
        assert 'buffer_minutes' in status
        assert status['buffer_minutes'] == 30
    
    def test_add_excluded_window(self, service):
        """Test adding window to exclusion list."""
        result = service.add_excluded_window("SecretApp")
        
        assert result['success'] is True
        assert "SecretApp" in result['excluded']
    
    def test_remove_excluded_window(self, service):
        """Test removing window from exclusion list."""
        service.add_excluded_window("TempExclude")
        result = service.remove_excluded_window("TempExclude")
        
        assert result['success'] is True
        assert "TempExclude" not in result['excluded']
    
    def test_get_frame_at_time(self, service):
        """Test temporal frame retrieval."""
        from services.rewind_service import RewindFrame
        
        # Add frames at different times
        now = datetime.now()
        
        with service._lock:
            service._buffer.append(RewindFrame(
                timestamp=now - timedelta(minutes=10),
                window_name="Old Window",
                image_base64="old",
                image_hash="hash1"
            ))
            service._buffer.append(RewindFrame(
                timestamp=now - timedelta(minutes=5),
                window_name="Recent Window",
                image_base64="recent",
                image_hash="hash2"
            ))
        
        # Get frame from ~5 minutes ago
        frame = service.get_frame_at_time(5)
        
        assert frame is not None
        assert frame.window_name == "Recent Window"
    
    def test_get_timeline(self, service):
        """Test timeline generation."""
        from services.rewind_service import RewindFrame
        
        now = datetime.now()
        # Populate buffer in chronological order (Oldest -> Newest)
        # i=4 (4 mins ago) -> i=0 (Now)
        with service._lock:
            for i in reversed(range(5)):
                service._buffer.append(RewindFrame(
                    timestamp=now - timedelta(minutes=i),
                    window_name=f"Window {i}",
                    image_base64=f"img{i}",
                    image_hash=f"hash{i}"
                ))
        
        timeline = service.get_timeline(limit=3)
        
        assert len(timeline) == 3
        # Should be ordered most recent first
        assert timeline[0]['window_name'] == "Window 0"


class TestRewindCompression:
    """Tests for image compression functionality."""
    
    @pytest.mark.skipif(True, reason="Requires Pillow")
    def test_compress_image_with_pillow(self):
        """Test image compression when Pillow is available."""
        from services.rewind_service import RewindService
        
        service = RewindService()
        
        # Create a simple test image (1x1 red pixel PNG)
        test_png = base64.b64encode(bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A  # PNG header
        ])).decode()
        
        # Should not throw
        result = service._compress_image(test_png, "image/png")
        assert isinstance(result, str)


class TestRewindQuery:
    """Tests for query functionality."""
    
    @pytest.fixture
    def service_with_frames(self):
        """Service with pre-populated frames."""
        from services.rewind_service import RewindService, RewindFrame
        
        service = RewindService()
        now = datetime.now()
        
        with service._lock:
            service._buffer.append(RewindFrame(
                timestamp=now - timedelta(minutes=5),
                window_name="VSCode",
                image_base64="test",
                image_hash="hash1",
                analyzed=True,
                analysis_text="User was editing Python code in main.py"
            ))
        
        return service
    
    def test_query_no_frames(self):
        """Test querying empty buffer."""
        from services.rewind_service import RewindService
        
        service = RewindService()
        result = service.query("What was I doing?")
        
        assert result['success'] is False
        assert 'error' in result
    
    def test_query_with_frames(self, service_with_frames):
        """Test querying with frames available."""
        with patch.object(service_with_frames, '_generate_answer', return_value="You were editing code"):
            result = service_with_frames.query("What was I doing?")
        
        assert result['success'] is True
        assert 'answer' in result

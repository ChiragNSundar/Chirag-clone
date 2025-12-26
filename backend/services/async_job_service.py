"""
Async Job Service - Manages background processing jobs.
"""
import threading
import uuid
from datetime import datetime
from typing import Dict, Callable, Any, Optional
from enum import Enum


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Job:
    """Represents a background processing job."""
    
    def __init__(self, job_id: str, job_type: str):
        self.id = job_id
        self.type = job_type
        self.status = JobStatus.PENDING
        self.progress = 0
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.completed_at = None
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'type': self.type,
            'status': self.status.value,
            'progress': self.progress,
            'result': self.result,
            'error': self.error,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class AsyncJobService:
    """Service for managing async background jobs."""
    
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
    
    def create_job(self, job_type: str) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())[:8]
        job = Job(job_id, job_type)
        
        with self._lock:
            self.jobs[job_id] = job
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self.jobs.get(job_id)
    
    def update_job(self, job_id: str, status: JobStatus = None, 
                   progress: int = None, result: Any = None, error: str = None):
        """Update job status."""
        job = self.jobs.get(job_id)
        if not job:
            return
        
        with self._lock:
            if status:
                job.status = status
                if status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    job.completed_at = datetime.now()
            if progress is not None:
                job.progress = progress
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
    
    def run_async(self, job_id: str, func: Callable, *args, **kwargs):
        """Run a function asynchronously and update job status."""
        def wrapper():
            try:
                self.update_job(job_id, status=JobStatus.PROCESSING, progress=10)
                result = func(*args, **kwargs)
                self.update_job(job_id, status=JobStatus.COMPLETED, progress=100, result=result)
            except Exception as e:
                self.update_job(job_id, status=JobStatus.FAILED, error=str(e))
        
        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
    
    def cleanup_old_jobs(self, max_age_minutes: int = 60):
        """Remove jobs older than max_age_minutes."""
        now = datetime.now()
        with self._lock:
            to_remove = []
            for job_id, job in self.jobs.items():
                age = (now - job.created_at).total_seconds() / 60
                if age > max_age_minutes and job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    to_remove.append(job_id)
            for job_id in to_remove:
                del self.jobs[job_id]


# Singleton instance
_async_job_service = None

def get_async_job_service() -> AsyncJobService:
    """Get the singleton async job service instance."""
    global _async_job_service
    if _async_job_service is None:
        _async_job_service = AsyncJobService()
    return _async_job_service

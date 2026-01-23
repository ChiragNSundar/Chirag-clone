"""
Local Training Service - Backend service for managing local LLM training jobs.

Features:
- Training job queue with priority
- Real-time progress tracking
- GPU monitoring
- Configuration presets
- Process management (start, stop, pause)
- Output streaming
"""
import os
import sys
import json
import asyncio
import subprocess
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from threading import Lock
import time

from config import Config
from services.logger import get_logger

logger = get_logger(__name__)


# ============= Enums and Data Classes =============

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModelSize(str, Enum):
    TINY = "tiny"      # < 1B params
    SMALL = "small"    # 1-3B params
    MEDIUM = "medium"  # 3-8B params
    LARGE = "large"    # 8-13B params
    XLARGE = "xlarge"  # 13B+ params


@dataclass
class TrainingProgress:
    """Real-time training progress data."""
    current_epoch: int = 0
    total_epochs: int = 0
    current_step: int = 0
    total_steps: int = 0
    loss: float = 0.0
    learning_rate: float = 0.0
    eval_loss: Optional[float] = None
    samples_per_second: float = 0.0
    eta_seconds: int = 0
    gpu_memory_used: float = 0.0
    gpu_utilization: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrainingConfig:
    """Training job configuration."""
    dataset_path: str
    model_name: str = "microsoft/phi-2"
    output_dir: str = "./adapters"
    
    # Training params
    num_epochs: int = 3
    batch_size: int = 2
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    max_seq_length: int = 2048
    
    # LoRA params
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    
    # Options
    use_unsloth: bool = True
    load_in_4bit: bool = True
    export_gguf: bool = False
    gguf_quantization: str = "q4_k_m"
    
    # Logging
    wandb_project: Optional[str] = None
    logging_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 100
    
    # Format
    format_type: str = "chatml"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'TrainingConfig':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class TrainingJob:
    """A training job with metadata and progress."""
    job_id: str
    config: TrainingConfig
    status: JobStatus = JobStatus.QUEUED
    progress: TrainingProgress = field(default_factory=TrainingProgress)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    output_path: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    priority: int = 0  # Higher = more priority
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "output_path": self.output_path,
            "logs": self.logs[-50:],  # Last 50 log lines
            "priority": self.priority,
        }


@dataclass
class GPUInfo:
    """GPU status information."""
    available: bool = False
    device_count: int = 0
    devices: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModelInfo:
    """Information about an available model."""
    name: str
    full_name: str
    size: ModelSize
    recommended_vram_gb: float
    max_seq_length: int
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "size": self.size.value,
            "recommended_vram_gb": self.recommended_vram_gb,
            "max_seq_length": self.max_seq_length,
            "description": self.description,
        }


@dataclass
class AdapterInfo:
    """Information about a trained adapter."""
    name: str
    path: str
    base_model: str
    created_at: datetime
    size_mb: float
    has_gguf: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "base_model": self.base_model,
            "created_at": self.created_at.isoformat(),
            "size_mb": self.size_mb,
            "has_gguf": self.has_gguf,
        }


# ============= Training Presets =============

TRAINING_PRESETS = {
    "quick": {
        "name": "Quick Test",
        "description": "Fast training for testing (1 epoch, high LR)",
        "config": {
            "num_epochs": 1,
            "batch_size": 4,
            "learning_rate": 5e-4,
            "lora_r": 8,
            "lora_alpha": 16,
            "save_steps": 50,
            "eval_steps": 50,
        }
    },
    "balanced": {
        "name": "Balanced",
        "description": "Good balance of speed and quality (3 epochs)",
        "config": {
            "num_epochs": 3,
            "batch_size": 2,
            "learning_rate": 2e-4,
            "lora_r": 16,
            "lora_alpha": 32,
            "save_steps": 100,
            "eval_steps": 100,
        }
    },
    "quality": {
        "name": "High Quality",
        "description": "Slower but higher quality (5 epochs, lower LR)",
        "config": {
            "num_epochs": 5,
            "batch_size": 1,
            "gradient_accumulation_steps": 8,
            "learning_rate": 1e-4,
            "lora_r": 32,
            "lora_alpha": 64,
            "save_steps": 50,
            "eval_steps": 50,
        }
    },
    "memory_efficient": {
        "name": "Memory Efficient",
        "description": "For GPUs with limited VRAM (< 8GB)",
        "config": {
            "num_epochs": 3,
            "batch_size": 1,
            "gradient_accumulation_steps": 8,
            "learning_rate": 2e-4,
            "lora_r": 8,
            "lora_alpha": 16,
            "max_seq_length": 1024,
            "save_steps": 200,
        }
    },
}


AVAILABLE_MODELS = [
    ModelInfo(
        name="tinyllama",
        full_name="unsloth/tinyllama-bnb-4bit",
        size=ModelSize.TINY,
        recommended_vram_gb=4,
        max_seq_length=2048,
        description="TinyLlama 1.1B - Great for testing and low-resource systems"
    ),
    ModelInfo(
        name="phi-2",
        full_name="unsloth/phi-2-bnb-4bit",
        size=ModelSize.SMALL,
        recommended_vram_gb=6,
        max_seq_length=2048,
        description="Microsoft Phi-2 2.7B - Excellent reasoning for its size"
    ),
    ModelInfo(
        name="phi-3-mini",
        full_name="unsloth/Phi-3-mini-4k-instruct-bnb-4bit",
        size=ModelSize.SMALL,
        recommended_vram_gb=8,
        max_seq_length=4096,
        description="Microsoft Phi-3 Mini 3.8B - Latest Phi model"
    ),
    ModelInfo(
        name="gemma-2b",
        full_name="unsloth/gemma-2b-bnb-4bit",
        size=ModelSize.SMALL,
        recommended_vram_gb=6,
        max_seq_length=2048,
        description="Google Gemma 2B - Efficient and capable"
    ),
    ModelInfo(
        name="gemma-7b",
        full_name="unsloth/gemma-7b-bnb-4bit",
        size=ModelSize.MEDIUM,
        recommended_vram_gb=12,
        max_seq_length=4096,
        description="Google Gemma 7B - Strong performance"
    ),
    ModelInfo(
        name="mistral-7b",
        full_name="unsloth/mistral-7b-bnb-4bit",
        size=ModelSize.MEDIUM,
        recommended_vram_gb=12,
        max_seq_length=4096,
        description="Mistral 7B - Excellent all-around model"
    ),
    ModelInfo(
        name="mistral-7b-instruct",
        full_name="unsloth/mistral-7b-instruct-v0.2-bnb-4bit",
        size=ModelSize.MEDIUM,
        recommended_vram_gb=12,
        max_seq_length=4096,
        description="Mistral 7B Instruct - Tuned for instructions"
    ),
    ModelInfo(
        name="llama3-8b",
        full_name="unsloth/llama-3-8b-bnb-4bit",
        size=ModelSize.MEDIUM,
        recommended_vram_gb=16,
        max_seq_length=8192,
        description="Meta Llama 3 8B - State-of-the-art open model"
    ),
    ModelInfo(
        name="llama3-8b-instruct",
        full_name="unsloth/llama-3-8b-Instruct-bnb-4bit",
        size=ModelSize.MEDIUM,
        recommended_vram_gb=16,
        max_seq_length=8192,
        description="Meta Llama 3 8B Instruct - Best for chat"
    ),
    ModelInfo(
        name="qwen2-7b",
        full_name="unsloth/Qwen2-7B-bnb-4bit",
        size=ModelSize.MEDIUM,
        recommended_vram_gb=12,
        max_seq_length=4096,
        description="Alibaba Qwen2 7B - Strong multilingual support"
    ),
]


# ============= Local Training Service =============

class LocalTrainingService:
    """
    Service for managing local LLM training jobs.
    
    Provides:
    - Job queue with priority
    - Real-time progress tracking
    - GPU monitoring
    - Process management
    """
    
    def __init__(self):
        self.jobs: Dict[str, TrainingJob] = {}
        self.job_queue: List[str] = []
        self.current_job_id: Optional[str] = None
        self.current_process: Optional[subprocess.Popen] = None
        self._lock = Lock()
        self._running = False
        self._worker_task = None
        
        # Paths
        self.adapters_dir = getattr(Config, 'LOCAL_ADAPTERS_DIR', './adapters')
        self.models_dir = getattr(Config, 'LOCAL_MODELS_DIR', './models')
        self.train_script = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "tools",
            "train_lora.py"
        )
        
        # Ensure directories exist
        os.makedirs(self.adapters_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        
        logger.info(f"LocalTrainingService initialized. Adapters dir: {self.adapters_dir}")
    
    # ============= Job Management =============
    
    def create_job(self, config: TrainingConfig, priority: int = 0) -> TrainingJob:
        """Create a new training job."""
        job_id = str(uuid.uuid4())[:8]
        
        # Set output directory
        run_name = f"lora-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{job_id}"
        config.output_dir = os.path.join(self.adapters_dir, run_name)
        
        job = TrainingJob(
            job_id=job_id,
            config=config,
            status=JobStatus.QUEUED,
            priority=priority,
            progress=TrainingProgress(total_epochs=config.num_epochs)
        )
        
        with self._lock:
            self.jobs[job_id] = job
            # Insert based on priority (higher priority first)
            insert_idx = 0
            for i, qid in enumerate(self.job_queue):
                if self.jobs[qid].priority < priority:
                    insert_idx = i
                    break
                insert_idx = i + 1
            self.job_queue.insert(insert_idx, job_id)
        
        logger.info(f"Created training job {job_id} with priority {priority}")
        return job
    
    def start_training(self, config: TrainingConfig, priority: int = 0) -> TrainingJob:
        """Quick method to create and queue a training job."""
        job = self.create_job(config, priority)
        
        # Start worker if not running
        if not self._running:
            self._start_worker()
        
        return job
    
    def get_job(self, job_id: str) -> Optional[TrainingJob]:
        """Get job by ID."""
        return self.jobs.get(job_id)
    
    def list_jobs(self, status: Optional[JobStatus] = None) -> List[TrainingJob]:
        """List all jobs, optionally filtered by status."""
        jobs = list(self.jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)
    
    def stop_job(self, job_id: str) -> bool:
        """Stop a running or queued job."""
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            
            if job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED
                if job_id in self.job_queue:
                    self.job_queue.remove(job_id)
                return True
            
            if job.status == JobStatus.RUNNING and job_id == self.current_job_id:
                if self.current_process:
                    self.current_process.terminate()
                    self.current_process = None
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now()
                self.current_job_id = None
                return True
        
        return False
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a completed/failed/cancelled job."""
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            
            if job.status in [JobStatus.QUEUED, JobStatus.RUNNING]:
                return False  # Can't delete active jobs
            
            del self.jobs[job_id]
            return True
    
    def get_job_logs(self, job_id: str, last_n: int = 100) -> List[str]:
        """Get logs for a specific job."""
        job = self.jobs.get(job_id)
        if not job:
            return []
        return job.logs[-last_n:]
    
    # ============= Training Execution =============
    
    def _start_worker(self):
        """Start the background worker that processes the job queue."""
        if self._running:
            return
        
        self._running = True
        # In a real async context, this would be an asyncio task
        import threading
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("Training worker started")
    
    def _stop_worker(self):
        """Stop the background worker."""
        self._running = False
    
    def _worker_loop(self):
        """Main worker loop that processes jobs from the queue."""
        while self._running:
            job_id = None
            
            with self._lock:
                if self.job_queue and not self.current_job_id:
                    job_id = self.job_queue.pop(0)
                    self.current_job_id = job_id
            
            if job_id:
                self._run_job(job_id)
            else:
                time.sleep(1)  # Wait before checking again
    
    def _run_job(self, job_id: str):
        """Execute a training job."""
        job = self.jobs.get(job_id)
        if not job:
            return
        
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        
        try:
            # Build command
            cmd = self._build_train_command(job.config)
            job.logs.append(f"Starting training: {' '.join(cmd)}")
            
            logger.info(f"Starting job {job_id}: {' '.join(cmd)}")
            
            # Run the training script
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            
            # Stream output
            for line in self.current_process.stdout:
                line = line.strip()
                job.logs.append(line)
                
                # Parse progress from output
                self._parse_progress(job, line)
                
                # Check if cancelled
                if job.status == JobStatus.CANCELLED:
                    break
            
            return_code = self.current_process.wait()
            
            if job.status != JobStatus.CANCELLED:
                if return_code == 0:
                    job.status = JobStatus.COMPLETED
                    job.output_path = job.config.output_dir
                    job.logs.append("Training completed successfully!")
                else:
                    job.status = JobStatus.FAILED
                    job.error_message = f"Training failed with exit code {return_code}"
                    job.logs.append(f"Training failed: exit code {return_code}")
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.logs.append(f"Error: {e}")
            logger.error(f"Job {job_id} failed: {e}")
        
        finally:
            job.completed_at = datetime.now()
            self.current_process = None
            self.current_job_id = None
    
    def _build_train_command(self, config: TrainingConfig) -> List[str]:
        """Build the command line for the training script."""
        cmd = [
            sys.executable,
            self.train_script,
            "--dataset", config.dataset_path,
            "--model", config.model_name,
            "--output", config.output_dir,
            "--epochs", str(config.num_epochs),
            "--batch-size", str(config.batch_size),
            "--gradient-accumulation", str(config.gradient_accumulation_steps),
            "--learning-rate", str(config.learning_rate),
            "--max-seq-length", str(config.max_seq_length),
            "--lora-r", str(config.lora_r),
            "--lora-alpha", str(config.lora_alpha),
            "--lora-dropout", str(config.lora_dropout),
            "--logging-steps", str(config.logging_steps),
            "--save-steps", str(config.save_steps),
            "--eval-steps", str(config.eval_steps),
            "--format", config.format_type,
        ]
        
        if config.use_unsloth:
            cmd.append("--use-unsloth")
        
        if not config.load_in_4bit:
            cmd.append("--no-4bit")
        
        if config.export_gguf:
            cmd.extend(["--export-gguf", "--gguf-quantization", config.gguf_quantization])
        
        if config.wandb_project:
            cmd.extend(["--wandb-project", config.wandb_project])
        
        return cmd
    
    def _parse_progress(self, job: TrainingJob, line: str):
        """Parse training progress from log line."""
        # Look for typical training output patterns
        # Example: "{'loss': 1.234, 'learning_rate': 0.0002, 'epoch': 1.5}"
        
        try:
            if "loss" in line.lower() and "{" in line:
                # Try to extract JSON-like dict
                start = line.find("{")
                end = line.rfind("}") + 1
                if start != -1 and end > start:
                    data = json.loads(line[start:end].replace("'", '"'))
                    
                    job.progress.loss = data.get("loss", job.progress.loss)
                    job.progress.learning_rate = data.get("learning_rate", job.progress.learning_rate)
                    
                    if "epoch" in data:
                        job.progress.current_epoch = int(data["epoch"])
            
            # Parse step info
            if "step" in line.lower():
                import re
                step_match = re.search(r'step\s*[=:]\s*(\d+)', line.lower())
                if step_match:
                    job.progress.current_step = int(step_match.group(1))
                
                total_match = re.search(r'(\d+)/(\d+)', line)
                if total_match:
                    job.progress.current_step = int(total_match.group(1))
                    job.progress.total_steps = int(total_match.group(2))
            
            # Parse epoch info
            if "epoch" in line.lower():
                import re
                epoch_match = re.search(r'epoch\s*[=:]\s*(\d+)', line.lower())
                if epoch_match:
                    job.progress.current_epoch = int(epoch_match.group(1))
                    
        except Exception:
            pass  # Ignore parsing errors
    
    # ============= GPU Monitoring =============
    
    def get_gpu_info(self) -> GPUInfo:
        """Get current GPU status."""
        info = GPUInfo()
        
        try:
            import torch
            if torch.cuda.is_available():
                info.available = True
                info.device_count = torch.cuda.device_count()
                
                for i in range(info.device_count):
                    props = torch.cuda.get_device_properties(i)
                    allocated = torch.cuda.memory_allocated(i)
                    reserved = torch.cuda.memory_reserved(i)
                    
                    device_info = {
                        "index": i,
                        "name": props.name,
                        "total_memory_gb": props.total_memory / 1e9,
                        "allocated_memory_gb": allocated / 1e9,
                        "reserved_memory_gb": reserved / 1e9,
                        "free_memory_gb": (props.total_memory - reserved) / 1e9,
                        "compute_capability": f"{props.major}.{props.minor}",
                    }
                    
                    # Try to get utilization via nvidia-smi
                    try:
                        result = subprocess.run(
                            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits", f"--id={i}"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            device_info["utilization_percent"] = float(result.stdout.strip())
                    except Exception:
                        pass
                    
                    info.devices.append(device_info)
                    
        except Exception as e:
            logger.warning(f"Could not get GPU info: {e}")
        
        return info
    
    # ============= Model and Adapter Management =============
    
    def get_available_models(self) -> List[ModelInfo]:
        """Get list of available base models."""
        return AVAILABLE_MODELS
    
    def get_training_presets(self) -> Dict[str, Any]:
        """Get available training presets."""
        return TRAINING_PRESETS
    
    def get_trained_adapters(self) -> List[AdapterInfo]:
        """List all trained adapters."""
        adapters = []
        
        if not os.path.exists(self.adapters_dir):
            return adapters
        
        for name in os.listdir(self.adapters_dir):
            adapter_path = os.path.join(self.adapters_dir, name)
            if not os.path.isdir(adapter_path):
                continue
            
            # Check for adapter files
            config_path = os.path.join(adapter_path, "training_config.json")
            adapter_config = os.path.join(adapter_path, "adapter_config.json")
            
            if not (os.path.exists(config_path) or os.path.exists(adapter_config)):
                continue
            
            # Get info
            try:
                base_model = "unknown"
                if os.path.exists(config_path):
                    with open(config_path) as f:
                        cfg = json.load(f)
                        base_model = cfg.get("model_name", "unknown")
                
                # Calculate size
                total_size = sum(
                    os.path.getsize(os.path.join(adapter_path, f))
                    for f in os.listdir(adapter_path)
                    if os.path.isfile(os.path.join(adapter_path, f))
                )
                
                # Check for GGUF
                gguf_dir = os.path.join(adapter_path, "gguf")
                has_gguf = os.path.exists(gguf_dir) and any(
                    f.endswith(".gguf") for f in os.listdir(gguf_dir)
                ) if os.path.exists(gguf_dir) else False
                
                # Get creation time
                created_at = datetime.fromtimestamp(os.path.getctime(adapter_path))
                
                adapters.append(AdapterInfo(
                    name=name,
                    path=adapter_path,
                    base_model=base_model,
                    created_at=created_at,
                    size_mb=total_size / 1e6,
                    has_gguf=has_gguf
                ))
                
            except Exception as e:
                logger.warning(f"Could not read adapter {name}: {e}")
        
        return sorted(adapters, key=lambda a: a.created_at, reverse=True)
    
    def delete_adapter(self, adapter_name: str) -> bool:
        """Delete a trained adapter."""
        import shutil
        
        adapter_path = os.path.join(self.adapters_dir, adapter_name)
        if not os.path.exists(adapter_path):
            return False
        
        try:
            shutil.rmtree(adapter_path)
            logger.info(f"Deleted adapter: {adapter_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete adapter {adapter_name}: {e}")
            return False
    
    def export_adapter_to_gguf(
        self,
        adapter_name: str,
        quantization: str = "q4_k_m"
    ) -> Optional[str]:
        """Export an adapter to GGUF format."""
        adapter_path = os.path.join(self.adapters_dir, adapter_name)
        if not os.path.exists(adapter_path):
            return None
        
        # Run export
        gguf_dir = os.path.join(adapter_path, "gguf")
        os.makedirs(gguf_dir, exist_ok=True)
        
        cmd = [
            sys.executable,
            self.train_script,
            "--dataset", "dummy",  # Not used for export
            "--model", adapter_path,
            "--output", gguf_dir,
            "--export-gguf",
            "--gguf-quantization", quantization,
            "--dry-run"  # Skip training
        ]
        
        # For now, just return the expected path
        # Actual export would require loading the model
        return os.path.join(gguf_dir, f"{adapter_name}-{quantization}.gguf")


# ============= Singleton =============

_local_training_service: Optional[LocalTrainingService] = None


def get_local_training_service() -> LocalTrainingService:
    """Get the singleton LocalTrainingService instance."""
    global _local_training_service
    if _local_training_service is None:
        _local_training_service = LocalTrainingService()
    return _local_training_service

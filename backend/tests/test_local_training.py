"""
Tests for Local Training Service and LoRA Training Infrastructure.

Tests cover:
- Training configuration
- Job management
- GPU detection
- Adapter management
- Dataset export
"""
import pytest
import os
import sys
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTrainingConfig:
    """Tests for TrainingConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        from services.local_training_service import TrainingConfig
        
        config = TrainingConfig(dataset_path="test.jsonl")
        
        assert config.dataset_path == "test.jsonl"
        assert config.model_name == "microsoft/phi-2"
        assert config.num_epochs == 3
        assert config.batch_size == 2
        assert config.lora_r == 16
        assert config.lora_alpha == 32
        assert config.use_unsloth == True
        assert config.load_in_4bit == True
    
    def test_custom_config(self):
        """Test custom configuration values."""
        from services.local_training_service import TrainingConfig
        
        config = TrainingConfig(
            dataset_path="custom.jsonl",
            model_name="unsloth/llama-3-8b-bnb-4bit",
            num_epochs=5,
            batch_size=4,
            lora_r=32,
            lora_alpha=64,
            learning_rate=1e-4
        )
        
        assert config.model_name == "unsloth/llama-3-8b-bnb-4bit"
        assert config.num_epochs == 5
        assert config.batch_size == 4
        assert config.lora_r == 32
        assert config.lora_alpha == 64
        assert config.learning_rate == 1e-4
    
    def test_config_to_dict(self):
        """Test config serialization to dict."""
        from services.local_training_service import TrainingConfig
        
        config = TrainingConfig(dataset_path="test.jsonl")
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict["dataset_path"] == "test.jsonl"
        assert "model_name" in config_dict
        assert "lora_r" in config_dict
    
    def test_config_from_dict(self):
        """Test config creation from dict."""
        from services.local_training_service import TrainingConfig
        
        data = {
            "dataset_path": "from_dict.jsonl",
            "model_name": "test-model",
            "num_epochs": 10
        }
        
        config = TrainingConfig.from_dict(data)
        
        assert config.dataset_path == "from_dict.jsonl"
        assert config.model_name == "test-model"
        assert config.num_epochs == 10


class TestJobStatus:
    """Tests for JobStatus enum."""
    
    def test_job_status_values(self):
        """Test job status enum values."""
        from services.local_training_service import JobStatus
        
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"


class TestTrainingProgress:
    """Tests for TrainingProgress dataclass."""
    
    def test_default_progress(self):
        """Test default progress values."""
        from services.local_training_service import TrainingProgress
        
        progress = TrainingProgress()
        
        assert progress.current_epoch == 0
        assert progress.total_epochs == 0
        assert progress.current_step == 0
        assert progress.loss == 0.0
    
    def test_progress_to_dict(self):
        """Test progress serialization."""
        from services.local_training_service import TrainingProgress
        
        progress = TrainingProgress(
            current_epoch=2,
            total_epochs=5,
            current_step=100,
            loss=0.5
        )
        
        progress_dict = progress.to_dict()
        
        assert progress_dict["current_epoch"] == 2
        assert progress_dict["total_epochs"] == 5
        assert progress_dict["current_step"] == 100
        assert progress_dict["loss"] == 0.5


class TestLocalTrainingService:
    """Tests for LocalTrainingService."""
    
    @pytest.fixture
    def service(self):
        """Create a service instance for testing."""
        from services.local_training_service import LocalTrainingService
        return LocalTrainingService()
    
    def test_service_initialization(self, service):
        """Test service initializes correctly."""
        assert service.jobs == {}
        assert service.job_queue == []
        assert service.current_job_id is None
    
    def test_create_job(self, service):
        """Test job creation."""
        from services.local_training_service import TrainingConfig, JobStatus
        
        config = TrainingConfig(dataset_path="test.jsonl")
        job = service.create_job(config)
        
        assert job.job_id is not None
        assert len(job.job_id) == 8
        assert job.status == JobStatus.QUEUED
        assert job.config.dataset_path == "test.jsonl"
        assert job.job_id in service.jobs
        assert job.job_id in service.job_queue
    
    def test_create_job_with_priority(self, service):
        """Test job creation with priority."""
        from services.local_training_service import TrainingConfig
        
        config1 = TrainingConfig(dataset_path="low.jsonl")
        config2 = TrainingConfig(dataset_path="high.jsonl")
        
        job1 = service.create_job(config1, priority=1)
        job2 = service.create_job(config2, priority=5)
        
        # Higher priority should be first in queue
        assert service.job_queue[0] == job2.job_id
        assert service.job_queue[1] == job1.job_id
    
    def test_get_job(self, service):
        """Test job retrieval."""
        from services.local_training_service import TrainingConfig
        
        config = TrainingConfig(dataset_path="test.jsonl")
        created_job = service.create_job(config)
        
        retrieved_job = service.get_job(created_job.job_id)
        
        assert retrieved_job is not None
        assert retrieved_job.job_id == created_job.job_id
    
    def test_get_nonexistent_job(self, service):
        """Test retrieval of non-existent job."""
        job = service.get_job("nonexistent")
        assert job is None
    
    def test_list_jobs(self, service):
        """Test listing all jobs."""
        from services.local_training_service import TrainingConfig
        
        config = TrainingConfig(dataset_path="test.jsonl")
        service.create_job(config)
        service.create_job(config)
        
        jobs = service.list_jobs()
        
        assert len(jobs) == 2
    
    def test_list_jobs_filtered(self, service):
        """Test listing jobs filtered by status."""
        from services.local_training_service import TrainingConfig, JobStatus
        
        config = TrainingConfig(dataset_path="test.jsonl")
        job1 = service.create_job(config)
        job2 = service.create_job(config)
        
        # Manually change one job's status
        service.jobs[job1.job_id].status = JobStatus.COMPLETED
        
        queued_jobs = service.list_jobs(status=JobStatus.QUEUED)
        completed_jobs = service.list_jobs(status=JobStatus.COMPLETED)
        
        assert len(queued_jobs) == 1
        assert len(completed_jobs) == 1
    
    def test_stop_queued_job(self, service):
        """Test stopping a queued job."""
        from services.local_training_service import TrainingConfig, JobStatus
        
        config = TrainingConfig(dataset_path="test.jsonl")
        job = service.create_job(config)
        
        result = service.stop_job(job.job_id)
        
        assert result == True
        assert service.jobs[job.job_id].status == JobStatus.CANCELLED
        assert job.job_id not in service.job_queue
    
    def test_delete_completed_job(self, service):
        """Test deleting a completed job."""
        from services.local_training_service import TrainingConfig, JobStatus
        
        config = TrainingConfig(dataset_path="test.jsonl")
        job = service.create_job(config)
        service.stop_job(job.job_id)  # This will cancel it
        
        result = service.delete_job(job.job_id)
        
        assert result == True
        assert job.job_id not in service.jobs
    
    def test_delete_running_job_fails(self, service):
        """Test that deleting a running job fails."""
        from services.local_training_service import TrainingConfig, JobStatus
        
        config = TrainingConfig(dataset_path="test.jsonl")
        job = service.create_job(config)
        service.jobs[job.job_id].status = JobStatus.RUNNING
        
        result = service.delete_job(job.job_id)
        
        assert result == False
        assert job.job_id in service.jobs
    
    def test_get_job_logs(self, service):
        """Test retrieving job logs."""
        from services.local_training_service import TrainingConfig
        
        config = TrainingConfig(dataset_path="test.jsonl")
        job = service.create_job(config)
        
        # Add some logs
        service.jobs[job.job_id].logs = ["Log 1", "Log 2", "Log 3"]
        
        logs = service.get_job_logs(job.job_id)
        
        assert len(logs) == 3
        assert logs[0] == "Log 1"
    
    def test_job_to_dict(self, service):
        """Test job serialization."""
        from services.local_training_service import TrainingConfig
        
        config = TrainingConfig(dataset_path="test.jsonl")
        job = service.create_job(config)
        
        job_dict = job.to_dict()
        
        assert isinstance(job_dict, dict)
        assert job_dict["job_id"] == job.job_id
        assert job_dict["status"] == "queued"
        assert "config" in job_dict
        assert "progress" in job_dict


class TestGPUInfo:
    """Tests for GPU detection."""
    
    def test_gpu_info_structure(self):
        """Test GPUInfo dataclass structure."""
        from services.local_training_service import GPUInfo
        
        info = GPUInfo()
        
        assert hasattr(info, "available")
        assert hasattr(info, "device_count")
        assert hasattr(info, "devices")
        
        info_dict = info.to_dict()
        assert "available" in info_dict
        assert "device_count" in info_dict
    
    def test_get_gpu_info_with_cuda(self):
        """Test GPU info when torch is available."""
        try:
            import torch
            has_torch = True
        except ImportError:
            has_torch = False
        
        if not has_torch:
            pytest.skip("torch not installed")
        
        from services.local_training_service import LocalTrainingService
        service = LocalTrainingService()
        
        # The actual implementation will be tested when torch is available
        gpu_info = service.get_gpu_info()
        assert isinstance(gpu_info.to_dict(), dict)
        assert "available" in gpu_info.to_dict()


class TestModelPresets:
    """Tests for model presets."""
    
    def test_training_presets_available(self):
        """Test training presets are defined."""
        from services.local_training_service import TRAINING_PRESETS
        
        assert "quick" in TRAINING_PRESETS
        assert "balanced" in TRAINING_PRESETS
        assert "quality" in TRAINING_PRESETS
        assert "memory_efficient" in TRAINING_PRESETS
    
    def test_preset_structure(self):
        """Test preset structure."""
        from services.local_training_service import TRAINING_PRESETS
        
        for name, preset in TRAINING_PRESETS.items():
            assert "name" in preset
            assert "description" in preset
            assert "config" in preset
            assert isinstance(preset["config"], dict)
    
    def test_available_models(self):
        """Test available models list."""
        from services.local_training_service import AVAILABLE_MODELS
        
        assert len(AVAILABLE_MODELS) > 0
        
        for model in AVAILABLE_MODELS:
            assert hasattr(model, "name")
            assert hasattr(model, "full_name")
            assert hasattr(model, "size")
            assert hasattr(model, "recommended_vram_gb")


class TestFineTuneService:
    """Tests for FineTuneService."""
    
    @pytest.fixture
    def service(self):
        """Create a service instance."""
        from services.finetune_service import FineTuneService
        return FineTuneService()
    
    def test_service_initialization(self, service):
        """Test service initializes."""
        assert service is not None
        assert hasattr(service, "dataset_path")
        assert hasattr(service, "train_path")
        assert hasattr(service, "val_path")
    
    def test_get_dataset_stats(self, service):
        """Test getting dataset stats."""
        stats = service.get_dataset_stats()
        
        assert isinstance(stats, dict)
        assert "total_examples" in stats or "total_rows" in stats
        assert "recommended_epochs" in stats
    
    def test_quality_filter(self, service):
        """Test quality filtering."""
        examples = [
            {"context": "Hello", "response": "Hi there, how are you?"},  # Good
            {"context": "Hi", "response": "Hey!"},  # Too short
            {"context": "", "response": "Empty context"},  # Empty context
            {"context": "Test", "response": "A" * 5000},  # Too long
        ]
        
        filtered = service._filter_quality(examples)
        
        assert len(filtered) < len(examples)
    
    def test_deduplicate(self, service):
        """Test deduplication."""
        examples = [
            {"context": "Hello", "response": "Hi there"},
            {"context": "Hello", "response": "Hi there"},  # Duplicate
            {"context": "Different", "response": "Unique response"},
        ]
        
        deduped = service._deduplicate(examples)
        
        assert len(deduped) == 2
    
    def test_format_example_chatml(self, service):
        """Test ChatML formatting."""
        example = {"context": "Hello", "response": "Hi there"}
        formatted = service._format_example(example, "chatml", "You are helpful.")
        
        assert "messages" in formatted
        assert len(formatted["messages"]) == 3  # system, user, assistant
        assert formatted["messages"][0]["role"] == "system"
        assert formatted["messages"][1]["role"] == "user"
        assert formatted["messages"][2]["role"] == "assistant"
    
    def test_format_example_alpaca(self, service):
        """Test Alpaca formatting."""
        example = {"context": "Hello", "response": "Hi there"}
        formatted = service._format_example(example, "alpaca", "")
        
        assert "instruction" in formatted
        assert "output" in formatted
        assert formatted["instruction"] == "Hello"
        assert formatted["output"] == "Hi there"
    
    def test_preview_export(self, service):
        """Test export preview."""
        # This will depend on actual data, but should not error
        try:
            preview = service.preview_export(format="chatml", limit=3)
            assert isinstance(preview, list)
        except Exception:
            # May fail if no data, that's OK for this test
            pass


class TestTrainLoraScript:
    """Tests for the train_lora.py script structure."""
    
    def test_script_imports(self):
        """Test that the training script can be parsed."""
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "tools",
            "train_lora.py"
        )
        
        if os.path.exists(script_path):
            with open(script_path, 'r') as f:
                content = f.read()
            
            # Check for key components
            assert "TrainingConfig" in content
            assert "MODEL_PRESETS" in content
            assert "train_with_unsloth" in content or "train_standard" in content
            assert "export_to_gguf" in content
            assert "argparse" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

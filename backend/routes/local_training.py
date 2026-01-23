"""
Local Training Routes - API endpoints for local LLM fine-tuning.

Provides REST API for:
- Starting and managing training jobs
- Monitoring training progress
- GPU status
- Model and adapter management
- Export functionality
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging
import asyncio

from services.local_training_service import (
    get_local_training_service,
    TrainingConfig,
    JobStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/training/local", tags=["local-training"])


# ============= Request/Response Models =============

class StartTrainingRequest(BaseModel):
    """Request to start a new training job."""
    dataset_path: str = Field(..., description="Path to the JSONL dataset")
    model_name: str = Field(default="unsloth/phi-2-bnb-4bit", description="Base model name")
    
    # Training parameters
    num_epochs: int = Field(default=3, ge=1, le=20)
    batch_size: int = Field(default=2, ge=1, le=32)
    gradient_accumulation_steps: int = Field(default=4, ge=1, le=64)
    learning_rate: float = Field(default=2e-4, ge=1e-6, le=1e-2)
    max_seq_length: int = Field(default=2048, ge=128, le=8192)
    
    # LoRA parameters
    lora_r: int = Field(default=16, ge=4, le=128)
    lora_alpha: int = Field(default=32, ge=8, le=256)
    lora_dropout: float = Field(default=0.05, ge=0.0, le=0.5)
    
    # Options
    use_unsloth: bool = Field(default=True, description="Use Unsloth optimizations")
    load_in_4bit: bool = Field(default=True, description="Load in 4-bit quantization")
    export_gguf: bool = Field(default=False, description="Export to GGUF after training")
    gguf_quantization: str = Field(default="q4_k_m", description="GGUF quantization method")
    
    # Logging
    wandb_project: Optional[str] = Field(default=None, description="WandB project name")
    logging_steps: int = Field(default=10, ge=1)
    save_steps: int = Field(default=100, ge=10)
    eval_steps: int = Field(default=100, ge=10)
    
    # Format
    format_type: str = Field(default="chatml", description="Dataset format type")
    
    # Priority
    priority: int = Field(default=0, ge=0, le=10, description="Job priority (higher = more priority)")


class StartFromPresetRequest(BaseModel):
    """Start training using a preset configuration."""
    dataset_path: str
    model_name: str = "unsloth/phi-2-bnb-4bit"
    preset: str = "balanced"
    priority: int = 0
    export_gguf: bool = False
    wandb_project: Optional[str] = None


class ExportGGUFRequest(BaseModel):
    """Request to export adapter to GGUF."""
    quantization: str = Field(default="q4_k_m", description="Quantization method")
    register_ollama: bool = Field(default=False, description="Register with Ollama")


class JobResponse(BaseModel):
    """Standard job response."""
    success: bool
    job_id: Optional[str] = None
    message: str


# ============= Training Job Endpoints =============

@router.post("/start")
async def start_training(request: StartTrainingRequest) -> Dict[str, Any]:
    """
    Start a new local training job.
    
    Creates a new fine-tuning job with the specified configuration.
    The job is queued and will start when GPU resources are available.
    """
    try:
        service = get_local_training_service()
        
        # Convert request to TrainingConfig
        config = TrainingConfig(
            dataset_path=request.dataset_path,
            model_name=request.model_name,
            num_epochs=request.num_epochs,
            batch_size=request.batch_size,
            gradient_accumulation_steps=request.gradient_accumulation_steps,
            learning_rate=request.learning_rate,
            max_seq_length=request.max_seq_length,
            lora_r=request.lora_r,
            lora_alpha=request.lora_alpha,
            lora_dropout=request.lora_dropout,
            use_unsloth=request.use_unsloth,
            load_in_4bit=request.load_in_4bit,
            export_gguf=request.export_gguf,
            gguf_quantization=request.gguf_quantization,
            wandb_project=request.wandb_project,
            logging_steps=request.logging_steps,
            save_steps=request.save_steps,
            eval_steps=request.eval_steps,
            format_type=request.format_type,
        )
        
        job = service.start_training(config, priority=request.priority)
        
        return {
            "success": True,
            "job_id": job.job_id,
            "message": f"Training job {job.job_id} created and queued",
            "job": job.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to start training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start-preset")
async def start_training_from_preset(request: StartFromPresetRequest) -> Dict[str, Any]:
    """
    Start training using a preset configuration.
    
    Available presets: quick, balanced, quality, memory_efficient
    """
    try:
        service = get_local_training_service()
        presets = service.get_training_presets()
        
        if request.preset not in presets:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown preset: {request.preset}. Available: {list(presets.keys())}"
            )
        
        preset_config = presets[request.preset]["config"]
        
        config = TrainingConfig(
            dataset_path=request.dataset_path,
            model_name=request.model_name,
            export_gguf=request.export_gguf,
            wandb_project=request.wandb_project,
            **preset_config
        )
        
        job = service.start_training(config, priority=request.priority)
        
        return {
            "success": True,
            "job_id": job.job_id,
            "preset": request.preset,
            "message": f"Training job {job.job_id} started with '{request.preset}' preset",
            "job": job.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start training from preset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs")
async def list_jobs(status: Optional[str] = None) -> Dict[str, Any]:
    """List all training jobs, optionally filtered by status."""
    try:
        service = get_local_training_service()
        
        job_status = None
        if status:
            try:
                job_status = JobStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Valid: {[s.value for s in JobStatus]}"
                )
        
        jobs = service.list_jobs(status=job_status)
        
        return {
            "success": True,
            "total": len(jobs),
            "jobs": [job.to_dict() for job in jobs]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> Dict[str, Any]:
    """Get details for a specific training job."""
    try:
        service = get_local_training_service()
        job = service.get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        
        return {
            "success": True,
            "job": job.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/stop")
async def stop_job(job_id: str) -> JobResponse:
    """Stop a running or queued training job."""
    try:
        service = get_local_training_service()
        success = service.stop_job(job_id)
        
        if success:
            return JobResponse(
                success=True,
                job_id=job_id,
                message=f"Job {job_id} stopped successfully"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Could not stop job {job_id}. It may have already completed."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> JobResponse:
    """Delete a completed, failed, or cancelled job."""
    try:
        service = get_local_training_service()
        success = service.delete_job(job_id)
        
        if success:
            return JobResponse(
                success=True,
                job_id=job_id,
                message=f"Job {job_id} deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Could not delete job {job_id}. It may be running or not exist."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(job_id: str, last_n: int = 100) -> Dict[str, Any]:
    """Get training logs for a job."""
    try:
        service = get_local_training_service()
        logs = service.get_job_logs(job_id, last_n=last_n)
        
        job = service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        
        return {
            "success": True,
            "job_id": job_id,
            "status": job.status.value,
            "log_count": len(logs),
            "logs": logs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get logs for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= GPU and System Info =============

@router.get("/gpu")
async def get_gpu_status() -> Dict[str, Any]:
    """Get current GPU status and availability."""
    try:
        service = get_local_training_service()
        gpu_info = service.get_gpu_info()
        
        return {
            "success": True,
            "gpu": gpu_info.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to get GPU info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system")
async def get_system_status() -> Dict[str, Any]:
    """Get overall system status for training."""
    try:
        service = get_local_training_service()
        gpu_info = service.get_gpu_info()
        jobs = service.list_jobs()
        
        running_jobs = [j for j in jobs if j.status == JobStatus.RUNNING]
        queued_jobs = [j for j in jobs if j.status == JobStatus.QUEUED]
        
        return {
            "success": True,
            "gpu_available": gpu_info.available,
            "gpu_count": gpu_info.device_count,
            "running_jobs": len(running_jobs),
            "queued_jobs": len(queued_jobs),
            "total_jobs": len(jobs),
            "current_job_id": running_jobs[0].job_id if running_jobs else None
        }
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Models and Presets =============

@router.get("/models")
async def get_available_models() -> Dict[str, Any]:
    """Get list of available base models for training."""
    try:
        service = get_local_training_service()
        models = service.get_available_models()
        gpu_info = service.get_gpu_info()
        
        # Add recommendation based on available VRAM
        available_vram = 0
        if gpu_info.available and gpu_info.devices:
            available_vram = gpu_info.devices[0].get("free_memory_gb", 0)
        
        models_data = []
        for model in models:
            model_dict = model.to_dict()
            model_dict["recommended"] = model.recommended_vram_gb <= available_vram
            models_data.append(model_dict)
        
        return {
            "success": True,
            "available_vram_gb": available_vram,
            "models": models_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presets")
async def get_training_presets() -> Dict[str, Any]:
    """Get available training presets."""
    try:
        service = get_local_training_service()
        presets = service.get_training_presets()
        
        return {
            "success": True,
            "presets": presets
        }
        
    except Exception as e:
        logger.error(f"Failed to get presets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Adapters =============

@router.get("/adapters")
async def list_adapters() -> Dict[str, Any]:
    """List all trained LoRA adapters."""
    try:
        service = get_local_training_service()
        adapters = service.get_trained_adapters()
        
        return {
            "success": True,
            "total": len(adapters),
            "adapters": [a.to_dict() for a in adapters]
        }
        
    except Exception as e:
        logger.error(f"Failed to list adapters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/adapters/{adapter_name}")
async def delete_adapter(adapter_name: str) -> Dict[str, Any]:
    """Delete a trained adapter."""
    try:
        service = get_local_training_service()
        success = service.delete_adapter(adapter_name)
        
        if success:
            return {
                "success": True,
                "message": f"Adapter '{adapter_name}' deleted successfully"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Adapter not found: {adapter_name}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete adapter {adapter_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/adapters/{adapter_name}/export-gguf")
async def export_adapter_gguf(
    adapter_name: str,
    request: ExportGGUFRequest
) -> Dict[str, Any]:
    """Export an adapter to GGUF format for llama.cpp/Ollama."""
    try:
        service = get_local_training_service()
        gguf_path = service.export_adapter_to_gguf(
            adapter_name,
            quantization=request.quantization
        )
        
        if gguf_path:
            return {
                "success": True,
                "message": f"Adapter exported to GGUF",
                "gguf_path": gguf_path,
                "quantization": request.quantization
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Adapter not found: {adapter_name}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export adapter {adapter_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= WebSocket for Real-time Progress =============

@router.websocket("/ws/{job_id}")
async def training_progress_websocket(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time training progress updates."""
    await websocket.accept()
    
    service = get_local_training_service()
    
    try:
        while True:
            job = service.get_job(job_id)
            
            if not job:
                await websocket.send_json({
                    "error": f"Job not found: {job_id}"
                })
                break
            
            # Send current status
            await websocket.send_json({
                "job_id": job_id,
                "status": job.status.value,
                "progress": job.progress.to_dict(),
                "logs": job.logs[-10:]  # Last 10 log lines
            })
            
            # Check if job is done
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                await websocket.send_json({
                    "job_id": job_id,
                    "status": job.status.value,
                    "final": True,
                    "output_path": job.output_path,
                    "error_message": job.error_message
                })
                break
            
            # Wait before next update
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass

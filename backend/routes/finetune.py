"""
Enhanced Fine-Tune Routes - Endpoints for dataset preparation and training management.

Provides:
- Dataset export with quality filtering and deduplication
- Multiple export formats (ChatML, Alpaca, ShareGPT, raw)
- Dataset statistics and analysis
- Export preview
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import logging
import os

from services.finetune_service import get_finetune_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/finetune", tags=["finetune"])


# ============= Request Models =============

class ExportRequest(BaseModel):
    """Request for dataset export."""
    format: str = Field(default="chatml", description="Export format: chatml, alpaca, sharegpt, raw")
    include_system: bool = Field(default=True, description="Include system prompt in examples")
    deduplicate: bool = Field(default=True, description="Remove near-duplicate examples")
    quality_filter: bool = Field(default=True, description="Filter low-quality examples")
    validation_split: float = Field(default=0.1, ge=0, le=0.5, description="Validation set fraction")
    shuffle: bool = Field(default=True, description="Shuffle before splitting")


class PreviewRequest(BaseModel):
    """Request for export preview."""
    format: str = Field(default="chatml")
    limit: int = Field(default=5, ge=1, le=20)


# ============= Endpoints =============

@router.get("/stats")
async def get_stats():
    """
    Get comprehensive dataset statistics.
    
    Returns:
        Statistics including example counts, length distributions, quality score
    """
    try:
        service = get_finetune_service()
        stats = service.get_dataset_stats()
        return {"success": True, **stats}
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze")
async def analyze_dataset():
    """
    Perform deep analysis of the dataset.
    
    Returns:
        Analysis including word frequency, length distribution, quality issues
    """
    try:
        service = get_finetune_service()
        analysis = service.analyze_dataset()
        return {"success": True, **analysis}
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_dataset(request: ExportRequest):
    """
    Export dataset to JSONL format with optional processing.
    
    Args:
        format: Output format (chatml, alpaca, sharegpt, raw)
        include_system: Include system prompt in each example
        deduplicate: Remove duplicate/similar examples
        quality_filter: Remove low-quality examples
        validation_split: Create train/val split
        shuffle: Shuffle data before splitting
    """
    try:
        service = get_finetune_service()
        result = service.export_dataset(
            format=request.format,
            include_system=request.include_system,
            deduplicate=request.deduplicate,
            quality_filter=request.quality_filter,
            validation_split=request.validation_split,
            shuffle=request.shuffle
        )
        return result
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview")
async def preview_export(request: PreviewRequest):
    """
    Preview what the exported dataset will look like.
    
    Args:
        format: Output format to preview
        limit: Number of examples to show
    """
    try:
        service = get_finetune_service()
        preview = service.preview_export(format=request.format, limit=request.limit)
        return {
            "success": True,
            "format": request.format,
            "examples": preview
        }
    except Exception as e:
        logger.error(f"Preview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download")
async def download_dataset():
    """Download the full exported dataset."""
    try:
        service = get_finetune_service()
        if os.path.exists(service.dataset_path):
            return FileResponse(
                service.dataset_path, 
                media_type='application/json', 
                filename='finetune_dataset.jsonl'
            )
        else:
            raise HTTPException(status_code=404, detail="Dataset not found. Please export first.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/train")
async def download_train_dataset():
    """Download the training split of the dataset."""
    try:
        service = get_finetune_service()
        if os.path.exists(service.train_path):
            return FileResponse(
                service.train_path, 
                media_type='application/json', 
                filename='train_dataset.jsonl'
            )
        else:
            raise HTTPException(status_code=404, detail="Training dataset not found. Please export with validation_split > 0.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download train error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/val")
async def download_val_dataset():
    """Download the validation split of the dataset."""
    try:
        service = get_finetune_service()
        if os.path.exists(service.val_path):
            return FileResponse(
                service.val_path, 
                media_type='application/json', 
                filename='val_dataset.jsonl'
            )
        else:
            raise HTTPException(status_code=404, detail="Validation dataset not found. Please export with validation_split > 0.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download val error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/formats")
async def list_formats():
    """List available export formats with descriptions."""
    return {
        "success": True,
        "formats": [
            {
                "name": "chatml",
                "description": "ChatML format (OpenAI, most LLMs)",
                "example": {"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
            },
            {
                "name": "alpaca",
                "description": "Alpaca format (Stanford Alpaca style)",
                "example": {"instruction": "...", "input": "", "output": "..."}
            },
            {
                "name": "sharegpt",
                "description": "ShareGPT format (conversation pairs)",
                "example": {"conversations": [{"from": "human", "value": "..."}, {"from": "gpt", "value": "..."}]}
            },
            {
                "name": "raw",
                "description": "Raw text format (simple prompt-response)",
                "example": {"text": "User: ...\nAssistant: ..."}
            }
        ]
    }

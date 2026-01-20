
"""
Fine-Tune Routes - Endpoints for dataset preparation and training management.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import os

from services.finetune_service import get_finetune_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/finetune", tags=["finetune"])

class ExportRequest(BaseModel):
    format: str = "chatml"

@router.get("/stats")
async def get_stats():
    """Get dataset statistics."""
    try:
        service = get_finetune_service()
        return service.get_dataset_stats()
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export")
async def export_dataset(request: ExportRequest):
    """Export dataset to JSONL."""
    try:
        service = get_finetune_service()
        path = service.export_dataset(request.format)
        return {"status": "success", "path": path, "message": "Dataset exported successfully"}
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download")
async def download_dataset():
    """Download the exported dataset."""
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
    except Exception as e:
        # If it's 404, re-raise, else 500
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

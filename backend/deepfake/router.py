
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any
from datetime import datetime
import shutil
import uuid

# Import auth
from auth.router import get_current_user
from database import db, get_next_sequence

# Deepfake model imports disabled - model too heavy for free deployment
# from .model.config import load_config
# from .model.pred_func import load_genconvit
# import torch
# import numpy as np
# from .alethia_forensics_pipeline import get_local_model, extract_frames, convert_frame_to_base64, is_model_available

# Model availability check - always returns False since model is disabled
def is_model_available():
    return False

router = APIRouter()

class DeepfakeResult(BaseModel):
    deepfakeId: str
    filename: str
    prediction: str
    confidence: float
    type: str  # 'video' or 'image'
    userId: str
    timestamp: datetime

@router.get("/status")
async def get_deepfake_status():
    """Check if deepfake model is available"""
    model_available = is_model_available()
    return {
        "model_available": model_available,
        "message": "Deepfake detection is currently disabled due to model size constraints for deployment."
    }

@router.post("/predict", response_model=DeepfakeResult)
async def predict_deepfake(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
) -> Any:
    # Model is disabled for deployment
    raise HTTPException(
        status_code=503,
        detail="Deepfake detection is currently disabled due to model size constraints. This feature will be enabled in future deployments with larger infrastructure."
    )
    
    # This code path should never be reached due to the check above
    # but kept for completeness
    pass


@router.get("/history")
async def get_deepfake_history(
    current_user: dict = Depends(get_current_user),
    limit: int = 50,
    skip: int = 0
):
    """Get deepfake detection history for the current user"""
    user_id = current_user.get("user_id") or str(current_user["_id"])
    
    cursor = db.deepfake_detections.find(
        {"userId": user_id}
    ).sort("created_at", -1).skip(skip).limit(limit)
    
    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    
    return {"detections": results, "count": len(results)}


@router.get("/{deepfake_id}")
async def get_deepfake_detection(
    deepfake_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific deepfake detection by ID"""
    user_id = current_user.get("user_id") or str(current_user["_id"])
    
    doc = await db.deepfake_detections.find_one({
        "deepfakeId": deepfake_id,
        "userId": user_id
    })
    
    if not doc:
        raise HTTPException(status_code=404, detail="Deepfake detection not found")
    
    doc["_id"] = str(doc["_id"])
    return doc


@router.delete("/{deepfake_id}")
async def delete_deepfake_detection(
    deepfake_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a deepfake detection by ID"""
    user_id = current_user.get("user_id") or str(current_user["_id"])
    
    result = await db.deepfake_detections.delete_one({
        "deepfakeId": deepfake_id,
        "userId": user_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Deepfake detection not found")
    
    return {"message": "Deepfake detection deleted successfully"}

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from typing import Union
from datetime import datetime
import sys
from pathlib import Path

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from auth.router import get_current_user
from database import db, get_next_sequence
from logger import get_logger
from ai_detection.service import (
    analyze_image_sightengine,
    analyze_video_sightengine,
    get_confidence_level,
)
from ai_detection.schema import AIDetectionResponse, AIDetectionStats

logger = get_logger(__name__)
router = APIRouter()

@router.post("/analyze-image", response_model=AIDetectionResponse)
async def analyze_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Analyze image for AI-generated content."""
    user_id = current_user.get("user_id") or str(current_user["_id"])
    logger.info(f"Image analysis requested by user {user_id}, filename={file.filename}")
    
    file_bytes = await file.read()
    logger.info(f"Image size: {len(file_bytes)} bytes")
    
    # Analyze with Sightengine
    result = await analyze_image_sightengine(file_bytes)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    # Extract AI score
    ai_score = result.get("type", {}).get("ai_generated", 0.0)
    is_ai_generated = ai_score > 0.5
    confidence_level = get_confidence_level(ai_score)
    
    # Save to MongoDB
    detection_seq = await get_next_sequence("ai_detections")
    detection_id = str(detection_seq)
    now = datetime.utcnow()
    
    detection_doc = {
        "detectionId": detection_id,
        "userId": user_id,
        "fileType": "image",
        "aiScore": ai_score,
        "isAiGenerated": is_ai_generated,
        "confidenceLevel": confidence_level,
        "sightengineResult": result,
        "createdAt": now,
        "updatedAt": now,
    }
    
    await db.ai_detections.insert_one(detection_doc)
    logger.info(f"Saved detection {detection_id} for user {user_id}")
    
    return AIDetectionResponse(
        detection_id=detection_id,
        ai_score=ai_score,
        is_ai_generated=is_ai_generated,
        confidence_level=confidence_level,
        sightengine_result=result,
        timestamp=now,
    )

@router.post("/analyze-video", response_model=AIDetectionResponse)
async def analyze_video(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Analyze video for AI-generated content."""
    user_id = current_user.get("user_id") or str(current_user["_id"])
    logger.info(f"Video analysis requested by user {user_id}, filename={file.filename}")
    
    file_bytes = await file.read()
    logger.info(f"Video size: {len(file_bytes)} bytes")
    
    # Analyze with Sightengine
    result = await analyze_video_sightengine(file_bytes)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    # Extract AI score from video frames
    # Video results have frames array: data.frames[].type.ai_generated
    frames = result.get("data", {}).get("frames", [])
    if frames:
        # Calculate average AI score from all frames
        frame_scores = [
            frame.get("type", {}).get("ai_generated", 0.0)
            for frame in frames
            if frame.get("type", {}).get("ai_generated") is not None
        ]
        if frame_scores:
            ai_score = sum(frame_scores) / len(frame_scores)
        else:
            ai_score = 0.0
    else:
        # Fallback to direct type path
        ai_score = result.get("type", {}).get("ai_generated", 0.0)
    
    is_ai_generated = ai_score > 0.5
    confidence_level = get_confidence_level(ai_score)
    
    # Save to MongoDB
    detection_seq = await get_next_sequence("ai_detections")
    detection_id = str(detection_seq)
    now = datetime.utcnow()
    
    detection_doc = {
        "detectionId": detection_id,
        "userId": user_id,
        "fileType": "video",
        "aiScore": ai_score,
        "isAiGenerated": is_ai_generated,
        "confidenceLevel": confidence_level,
        "sightengineResult": result,
        "createdAt": now,
        "updatedAt": now,
    }
    
    await db.ai_detections.insert_one(detection_doc)
    logger.info(f"Saved detection {detection_id} for user {user_id}")
    
    return AIDetectionResponse(
        detection_id=detection_id,
        ai_score=ai_score,
        is_ai_generated=is_ai_generated,
        confidence_level=confidence_level,
        sightengine_result=result,
        timestamp=now,
    )

@router.get("/stats", response_model=AIDetectionStats)
async def get_detection_stats(
    current_user: dict = Depends(get_current_user),
):
    """Get AI detection statistics for current user."""
    user_id = current_user.get("user_id") or str(current_user["_id"])
    
    query = {
        "$or": [
            {"userId": user_id},
            {"userId": {"$in": [int(user_id), str(user_id)]}},
        ]
    }
    
    detections = await db.ai_detections.find(query).to_list(length=None)
    
    total = len(detections)
    ai_generated = sum(1 for d in detections if d.get("isAiGenerated", False))
    human_generated = total - ai_generated
    avg_score = sum(d.get("aiScore", 0.0) for d in detections) / total if total > 0 else 0.0
    
    return AIDetectionStats(
        total_detections=total,
        ai_generated_count=ai_generated,
        human_generated_count=human_generated,
        average_ai_score=round(avg_score, 3),
    )


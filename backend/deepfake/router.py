
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

# Import GenConViT logic from alethia_forensics_pipeline
from .model.config import load_config
from .model.pred_func import load_genconvit
import torch
import numpy as np
from .alethia_forensics_pipeline import get_local_model, extract_frames, convert_frame_to_base64, is_model_available

# New analysis functions for modular structure
def run_local_analysis_only(video_path, num_frames=30):
    frames = extract_frames(video_path, num_frames=num_frames)
    if not frames:
        return {"status": "error", "message": "No frames extracted from video."}
    model = get_local_model()
    if model is None:
        return {"status": "error", "message": "Model not available. Weights folder not found."}
    from .model.face_rec import face_rec
    from .model.preprocess import preprocess_frame
    from .model.pred_vid import pred_vid
    face_images, face_count = face_rec(frames)
    if face_count == 0:
        return {"status": "error", "message": "No faces found in video frames."}
    face_tensor = preprocess_frame(face_images)
    if face_tensor is None or face_tensor.nelement() == 0:
        return {"status": "error", "message": "Preprocessing frames resulted in empty tensor."}
    face_tensor = face_tensor.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    y, y_val, mean_real, mean_fake = pred_vid(face_tensor, model)
    return {"status": "success", "average_score": y_val, "prediction_class": y, "mean_real": mean_real, "mean_fake": mean_fake}

def run_image_local_analysis(image_path):
    import cv2
    img = cv2.imread(image_path)
    if img is None:
        return {"status": "error", "message": "Could not read image file."}
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    model = get_local_model()
    if model is None:
        return {"status": "error", "message": "Model not available. Weights folder not found."}
    from .model.face_rec import face_rec
    from .model.preprocess import preprocess_frame
    from .model.pred_vid import pred_vid
    face_images, face_count = face_rec([img_rgb])
    if face_count == 0:
        return {"status": "error", "message": "No faces found in image."}
    face_tensor = preprocess_frame(face_images)
    if face_tensor is None or face_tensor.nelement() == 0:
        return {"status": "error", "message": "Preprocessing image resulted in empty tensor."}
    face_tensor = face_tensor.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    y, y_val, mean_real, mean_fake = pred_vid(face_tensor, model)
    return {"status": "success", "average_score": y_val, "prediction_class": y, "mean_real": mean_real, "mean_fake": mean_fake}

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
        "message": "Model weights are available" if model_available else "Model weights not found. Please add weights folder to enable deepfake detection."
    }

@router.post("/predict", response_model=DeepfakeResult)
async def predict_deepfake(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
) -> Any:
    # Check if model is available first
    if not is_model_available():
        raise HTTPException(
            status_code=503,
            detail="Deepfake detection is currently unavailable. Model weights not found. Please add the weights folder to enable this feature."
        )
    
    # Save uploaded file to a temp location
    file_ext = os.path.splitext(file.filename)[-1].lower()
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}{file_ext}")
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        if file_ext in [".mp4", ".avi", ".mov", ".mpeg", ".mpg"]:
            # Video file
            result = run_local_analysis_only(temp_path, num_frames=30)
            if result["status"] != "success":
                raise HTTPException(status_code=400, detail=result["message"])
            
            # Always return REAL or FAKE based on prediction class: 1 = REAL, 0 = FAKE
            prediction = "REAL" if result["prediction_class"] == 1 else "FAKE"
            
            confidence = float(result["average_score"])
            dtype = "video"
            # Log for debugging
            print(f"[Deepfake Debug] mean_real={result['mean_real']:.4f}, mean_fake={result['mean_fake']:.4f}, pred_class={result['prediction_class']}, confidence={confidence:.4f}, verdict={prediction}")
        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp"]:
            # Image file
            result = run_image_local_analysis(temp_path)
            if result["status"] != "success":
                raise HTTPException(status_code=400, detail=result["message"])
            
            # Always return REAL or FAKE based on prediction class: 1 = REAL, 0 = FAKE
            prediction = "REAL" if result["prediction_class"] == 1 else "FAKE"
            
            confidence = float(result["average_score"])
            dtype = "image"
            print(f"[Deepfake Debug] mean_real={result['mean_real']:.4f}, mean_fake={result['mean_fake']:.4f}, pred_class={result['prediction_class']}, confidence={confidence:.4f}, verdict={prediction}")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type.")

        # Get user ID
        user_id = current_user.get("user_id") or str(current_user["_id"])
        
        # Generate deepfake sequence ID
        deepfake_seq = await get_next_sequence("deepfakes")
        deepfake_id = str(deepfake_seq)
        
        # Get file size
        file_size = os.path.getsize(temp_path)
        
        # Current timestamp
        now = datetime.utcnow()
        
        # Save result to MongoDB
        try:
            deepfake_doc = {
                "deepfakeId": deepfake_id,
                "userId": user_id,
                "filename": file.filename,
                "file_extension": file_ext,
                "file_size": file_size,
                "prediction": prediction,
                "confidence": confidence,
                "prediction_class": result["prediction_class"],
                "type": dtype,
                "metadata": {
                    "model": "GenConViT",
                    "num_frames": 30 if dtype == "video" else 1,
                    "device": "cuda" if torch.cuda.is_available() else "cpu"
                },
                "created_at": now,
                "updated_at": now,
            }
            await db.deepfake_detections.insert_one(deepfake_doc)
        except Exception as e:
            # Log the error but don't fail the request
            import logging
            logging.warning(f"Failed to save result to MongoDB: {e}")

        return DeepfakeResult(
            deepfakeId=deepfake_id,
            filename=file.filename,
            prediction=prediction,
            confidence=confidence,
            type=dtype,
            userId=str(user_id),
            timestamp=now
        )
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


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

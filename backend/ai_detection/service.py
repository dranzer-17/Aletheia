import httpx
import os
from typing import Dict, Any
from pathlib import Path
import sys

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from logger import get_logger
from config import SIGHTENGINE_API_USER, SIGHTENGINE_API_SECRET

logger = get_logger(__name__)

async def analyze_image_sightengine(file_bytes: bytes) -> Dict[str, Any]:
    """Analyze image using Sightengine API."""
    url = "https://api.sightengine.com/1.0/check.json"
    
    data = {
        "models": "genai",
        "api_user": SIGHTENGINE_API_USER,
        "api_secret": SIGHTENGINE_API_SECRET,
    }
    
    files = {"media": ("upload", file_bytes)}
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(url, data=data, files=files)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Sightengine image analysis error: {e}")
        return {"error": str(e)}

async def analyze_video_sightengine(file_bytes: bytes) -> Dict[str, Any]:
    """Analyze video using Sightengine API."""
    url = "https://api.sightengine.com/1.0/video/check-sync.json"
    
    data = {
        "models": "genai",
        "api_user": SIGHTENGINE_API_USER,
        "api_secret": SIGHTENGINE_API_SECRET,
    }
    
    files = {"media": ("video.mp4", file_bytes)}
    
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(url, data=data, files=files)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Sightengine video analysis error: {e}")
        return {"error": str(e)}

def get_confidence_level(ai_score: float) -> str:
    """Determine confidence level based on AI score."""
    if ai_score > 0.75:
        return "High"
    elif ai_score > 0.40:
        return "Medium"
    else:
        return "Low"


from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AIDetectionResponse(BaseModel):
    detection_id: str
    ai_score: float
    is_ai_generated: bool
    confidence_level: str
    sightengine_result: dict
    timestamp: datetime

class AIDetectionStats(BaseModel):
    total_detections: int
    ai_generated_count: int
    human_generated_count: int
    average_ai_score: float


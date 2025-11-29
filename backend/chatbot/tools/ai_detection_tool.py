import sys
from pathlib import Path
from typing import Dict, Any, Optional
import httpx

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from logger import get_logger
from ai_detection.service import analyze_image_sightengine, analyze_video_sightengine, get_confidence_level
from config import SIGHTENGINE_API_USER, SIGHTENGINE_API_SECRET

logger = get_logger(__name__)

class AIDetectionTool:
    """Tool for AI content detection."""
    
    def __init__(self):
        self.name = "ai_detection"
        self.description = "Detects AI-generated content in images and videos using Sightengine"
    
    async def execute(
        self,
        file_bytes: bytes,
        file_type: str,  # "image" or "video"
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """Execute AI detection on media file."""
        try:
            if progress_callback:
                await progress_callback(f"Analyzing {file_type} for AI-generated content...")
            
            # Analyze with Sightengine
            if file_type == "image":
                result = await analyze_image_sightengine(file_bytes)
            else:
                result = await analyze_video_sightengine(file_bytes)
            
            if "error" in result:
                raise Exception(result["error"])
            
            # Extract AI score
            if file_type == "video":
                # Video has frames array
                frames = result.get("data", {}).get("frames", [])
                if frames:
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
                    ai_score = result.get("type", {}).get("ai_generated", 0.0)
            else:
                ai_score = result.get("type", {}).get("ai_generated", 0.0)
            
            is_ai_generated = ai_score > 0.5
            confidence_level = get_confidence_level(ai_score)
            
            # Format response
            response_html = self._format_response(ai_score, is_ai_generated, confidence_level)
            
            return {
                "success": True,
                "response": response_html,
                "sources": [],
                "metadata": {
                    "ai_score": ai_score,
                    "is_ai_generated": is_ai_generated,
                    "confidence_level": confidence_level,
                },
            }
            
        except Exception as e:
            logger.error(f"AI detection tool error: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"<p>Error detecting AI content: {str(e)}</p>",
                "sources": [],
                "metadata": {},
            }
    
    def _format_response(self, ai_score: float, is_ai_generated: bool, confidence_level: str) -> str:
        """Format response as HTML."""
        color = "red" if confidence_level == "High" else ("yellow" if confidence_level == "Medium" else "green")
        status = "AI Generated" if is_ai_generated else "Human Generated"
        
        html = f"""
        <div>
            <h3 style="color: {color}; margin-bottom: 12px;">Status: {status}</h3>
            <p style="margin-bottom: 12px;"><strong>AI Score:</strong> {ai_score * 100:.1f}%</p>
            <p style="margin-bottom: 12px;"><strong>Confidence Level:</strong> {confidence_level}</p>
            <p>
                {self._get_interpretation(confidence_level)}
            </p>
        </div>
        """
        return html.strip()
    
    def _get_interpretation(self, level: str) -> str:
        if level == "High":
            return "High probability of AI-generated content detected."
        elif level == "Medium":
            return "Medium probability - content may be AI-generated."
        else:
            return "Low probability - content appears to be human-generated."


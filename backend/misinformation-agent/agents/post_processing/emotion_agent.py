from typing import Dict, Any
import importlib.util
import json
import re
from pathlib import Path
import sys

from models.claim import Claim

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from logger import get_logger


def _load_app_config():
    config_path = Path(__file__).resolve().parents[2] / "config.py"
    spec = importlib.util.spec_from_file_location("misinfo_app_config_emotion", config_path)
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load misinformation-agent APP_CONFIG.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    if not hasattr(module, "APP_CONFIG"):
        raise AttributeError("APP_CONFIG missing in misinformation-agent config.")
    return module.APP_CONFIG


APP_CONFIG = _load_app_config()

logger = get_logger(__name__)
SEPARATOR = "-" * 100

# Emotion labels (6 basic emotions)
EMOTION_LABELS = ["joy", "anger", "sadness", "fear", "surprise", "disgust"]


def extract_json_from_text(text: str) -> str | None:
    """Extract JSON from LLM response text."""
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    if text.strip().startswith('{'):
        return text
    logger.error(f"Could not find a valid JSON block in the LLM response: {text}")
    return None


def normalize_to_percentages(scores: Dict[str, float]) -> Dict[str, float]:
    """
    Normalize scores to percentages that sum to 100%.
    
    Args:
        scores: Dictionary with emotion -> score (0.0-1.0)
    
    Returns:
        Dictionary with emotion -> percentage (0.0-100.0)
    """
    total = sum(scores.values())
    
    if total == 0:
        # Fallback: equal distribution
        equal_percent = 100.0 / len(scores)
        return {emotion: equal_percent for emotion in scores.keys()}
    
    # Normalize to percentages
    percentages = {emotion: (score / total) * 100.0 for emotion, score in scores.items()}
    
    # Round to 1 decimal place
    percentages = {emotion: round(percent, 1) for emotion, percent in percentages.items()}
    
    # Ensure sum is exactly 100.0 (adjust for rounding errors)
    current_sum = sum(percentages.values())
    if abs(current_sum - 100.0) > 0.1:
        # Adjust the highest value to make sum = 100.0
        diff = 100.0 - current_sum
        max_emotion = max(percentages.items(), key=lambda x: x[1])[0]
        percentages[max_emotion] = round(percentages[max_emotion] + diff, 1)
    
    return percentages


async def analyze_emotion_llm(claim_text: str, llm_client: Any) -> Dict[str, Any]:
    """
    Analyze emotions using LLM.
    
    Args:
        claim_text: The claim text to analyze
        llm_client: LLM client instance
    
    Returns:
        Dictionary with emotion analysis results
    """
    logger.info("Analyzing emotions using LLM...")
    
    prompt = f"""
You are an expert emotion analyzer. Analyze the emotions present in the following text and provide a detailed emotion breakdown.

**Text to Analyze:** "{claim_text}"

**Task:**
1. Identify which of the 6 basic emotions are present: joy, anger, sadness, fear, surprise, disgust
2. Assign intensity scores (0.0 to 1.0) for each emotion
3. The scores should reflect how much of each emotion is present in the text
4. Scores should be relative - if text is mostly joyful, joy should have the highest score
5. Multiple emotions can be present simultaneously

**Available Emotions:**
- joy: Happiness, pleasure, contentment
- anger: Rage, irritation, frustration
- sadness: Sorrow, grief, melancholy
- fear: Anxiety, worry, terror
- surprise: Shock, astonishment, amazement
- disgust: Revulsion, distaste, repulsion

**Output Format (JSON ONLY, no markdown, no explanations):**
{{
  "joy": 0.45,
  "anger": 0.05,
  "sadness": 0.10,
  "fear": 0.15,
  "surprise": 0.20,
  "disgust": 0.05
}}

The scores must be between 0.0 and 1.0, and should reflect the relative presence of each emotion in the text.
"""
    
    try:
        response = await llm_client.model.generate_content_async(prompt)
        json_string = extract_json_from_text(response.text)
        
        if not json_string:
            raise ValueError("No JSON found in LLM response.")
        
        raw_scores = json.loads(json_string)
        
        # Validate and ensure all emotions are present
        for emotion in EMOTION_LABELS:
            if emotion not in raw_scores:
                raw_scores[emotion] = 0.0
            else:
                # Clamp values to 0.0-1.0 range
                raw_scores[emotion] = max(0.0, min(1.0, float(raw_scores[emotion])))
        
        # Normalize to percentages
        emotion_distribution = normalize_to_percentages(raw_scores)
        
        # Find primary emotion (highest score)
        primary_emotion = max(emotion_distribution.items(), key=lambda x: x[1])[0]
        confidence = raw_scores.get(primary_emotion, 0.0)
        
        return {
            "primary_emotion": primary_emotion,
            "emotion_distribution": emotion_distribution,
            "raw_scores": {k: round(v, 4) for k, v in raw_scores.items()},
            "confidence": round(confidence, 4),
            "model": "LLM (Gemini)"
        }
        
    except Exception as e:
        logger.error(f"LLM Emotion analysis failed: {e}", exc_info=True)
        # Return neutral fallback with equal distribution
        equal_percent = 100.0 / len(EMOTION_LABELS)
        return {
            "primary_emotion": "neutral",
            "emotion_distribution": {emotion: round(equal_percent, 1) for emotion in EMOTION_LABELS},
            "raw_scores": {emotion: round(1.0 / len(EMOTION_LABELS), 4) for emotion in EMOTION_LABELS},
            "confidence": round(1.0 / len(EMOTION_LABELS), 4),
            "model": "LLM (Gemini)",
            "error": str(e)
        }


async def run(claim: Claim, llm_client: Any) -> Dict[str, Any]:
    """
    Analyze emotions in a claim using LLM.
    
    Args:
        claim: The claim object to analyze
        llm_client: LLM client instance
    
    Returns:
        Dictionary with emotion analysis results including percentages
    """
    logger.info(SEPARATOR)
    logger.info("--- EMOTION ANALYSIS AGENT (LLM) BEING CALLED ---")
    logger.info(f"Analyzing emotions for claim: '{claim.text[:100]}...'")
    
    result = await analyze_emotion_llm(claim.text, llm_client)
    
    logger.info(f"Primary Emotion: {result['primary_emotion']}")
    logger.info(f"Emotion Distribution: {result['emotion_distribution']}")
    logger.info(f"Confidence: {result['confidence']:.2%}")
    
    logger.info("--- EMOTION ANALYSIS AGENT FINISHED ---")
    logger.info(SEPARATOR)
    
    return result

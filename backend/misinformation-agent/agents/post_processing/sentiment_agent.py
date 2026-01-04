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

# Import rate limiter
UTILS_ROOT = Path(__file__).resolve().parents[2] / "utils"
if str(UTILS_ROOT) not in sys.path:
    sys.path.insert(0, str(UTILS_ROOT))
from rate_limiter import gemini_rate_limiter, with_rate_limit_retry


def _load_app_config():
    config_path = Path(__file__).resolve().parents[2] / "config.py"
    spec = importlib.util.spec_from_file_location("misinfo_app_config_sentiment", config_path)
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

# Sentiment labels
SENTIMENT_LABELS = ["positive", "neutral", "negative"]


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
        scores: Dictionary with label -> score (0.0-1.0)
    
    Returns:
        Dictionary with label -> percentage (0.0-100.0)
    """
    total = sum(scores.values())
    
    if total == 0:
        # Fallback: equal distribution
        equal_percent = 100.0 / len(scores)
        return {label: equal_percent for label in scores.keys()}
    
    # Normalize to percentages
    percentages = {label: (score / total) * 100.0 for label, score in scores.items()}
    
    # Round to 1 decimal place
    percentages = {label: round(percent, 1) for label, percent in percentages.items()}
    
    # Ensure sum is exactly 100.0 (adjust for rounding errors)
    current_sum = sum(percentages.values())
    if abs(current_sum - 100.0) > 0.1:
        # Adjust the highest value to make sum = 100.0
        diff = 100.0 - current_sum
        max_label = max(percentages.items(), key=lambda x: x[1])[0]
        percentages[max_label] = round(percentages[max_label] + diff, 1)
    
    return percentages


async def _call_llm_for_sentiment(claim_text: str, llm_client: Any) -> Any:
    """
    Internal function to call LLM for sentiment analysis.
    Separated for rate limiting and retry logic.
    """
    prompt = f"""
You are an expert sentiment analyzer. Analyze the sentiment of the following text and provide a detailed sentiment breakdown.

**Text to Analyze:** "{claim_text}"

**Task:**
1. Determine the overall sentiment: positive, neutral, or negative
2. Assign intensity scores (0.0 to 1.0) for each sentiment category
3. The scores should reflect how much of each sentiment is present in the text
4. Scores should be relative - if text is mostly positive, positive should have the highest score

**Output Format (JSON ONLY, no markdown, no explanations):**
{{
  "positive": 0.65,
  "neutral": 0.25,
  "negative": 0.10
}}

The scores must be between 0.0 and 1.0, and should reflect the relative presence of each sentiment in the text.
"""
    return await llm_client.model.generate_content_async(prompt)


async def analyze_sentiment_llm(claim_text: str, llm_client: Any) -> Dict[str, Any]:
    """
    Analyze sentiment using LLM with rate limiting and retry logic.
    
    Args:
        claim_text: The claim text to analyze
        llm_client: LLM client instance
    
    Returns:
        Dictionary with sentiment analysis results
    """
    logger.info("Analyzing sentiment using LLM...")
    
    try:
        # Call LLM with rate limiting and retry
        response = await with_rate_limit_retry(
            gemini_rate_limiter,
            _call_llm_for_sentiment,
            claim_text,
            llm_client
        )
        json_string = extract_json_from_text(response.text)
        
        if not json_string:
            raise ValueError("No JSON found in LLM response.")
        
        raw_scores = json.loads(json_string)
        
        # Validate and ensure all labels are present
        for label in SENTIMENT_LABELS:
            if label not in raw_scores:
                raw_scores[label] = 0.0
            else:
                # Clamp values to 0.0-1.0 range
                raw_scores[label] = max(0.0, min(1.0, float(raw_scores[label])))
        
        # Normalize to percentages
        sentiment_distribution = normalize_to_percentages(raw_scores)
        
        # Find primary sentiment (highest score)
        primary_sentiment = max(sentiment_distribution.items(), key=lambda x: x[1])[0]
        confidence = raw_scores.get(primary_sentiment, 0.0)
        
        return {
            "primary_sentiment": primary_sentiment,
            "sentiment_distribution": sentiment_distribution,
            "raw_scores": {k: round(v, 4) for k, v in raw_scores.items()},
            "confidence": round(confidence, 4),
            "model": "LLM (Gemini)"
        }
        
    except Exception as e:
        logger.error(f"LLM Sentiment analysis failed: {e}", exc_info=True)
        # Return neutral fallback
        return {
            "primary_sentiment": "neutral",
            "sentiment_distribution": {
                "positive": 33.3,
                "neutral": 33.4,
                "negative": 33.3
            },
            "raw_scores": {
                "positive": 0.333,
                "neutral": 0.334,
                "negative": 0.333
            },
            "confidence": 0.333,
            "model": "LLM (Gemini)",
            "error": str(e)
        }


async def run(claim: Claim, llm_client: Any) -> Dict[str, Any]:
    """
    Analyze sentiment of a claim using LLM.
    
    Args:
        claim: The claim object to analyze
        llm_client: LLM client instance
    
    Returns:
        Dictionary with sentiment analysis results including percentages
    """
    logger.info(SEPARATOR)
    logger.info("--- SENTIMENT ANALYSIS AGENT (LLM) BEING CALLED ---")
    logger.info(f"Analyzing sentiment for claim: '{claim.text[:100]}...'")
    
    result = await analyze_sentiment_llm(claim.text, llm_client)
    
    logger.info(f"Primary Sentiment: {result['primary_sentiment']}")
    logger.info(f"Sentiment Distribution: {result['sentiment_distribution']}")
    logger.info(f"Confidence: {result['confidence']:.2%}")
    
    logger.info("--- SENTIMENT ANALYSIS AGENT FINISHED ---")
    logger.info(SEPARATOR)
    
    return result

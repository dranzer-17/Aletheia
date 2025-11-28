from typing import Any, Dict
import sys
from pathlib import Path

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from logger import get_logger

logger = get_logger(__name__)
SEPARATOR = "-" * 100

async def run(claim_text: str, llm_client: Any) -> Dict:
    """
    Analyzes a claim using an LLM to classify it and extract keywords.
    """
    logger.info(SEPARATOR)
    logger.info("--- CLAIM CLASSIFIER AGENT BEING CALLED ---")
    logger.info(f"Classifying claim: '{claim_text}'")

    classification_result = await llm_client.classify_claim(claim_text)
    
    logger.info(f"Claim classified as: Category='{classification_result.get('category')}', Sub-Category='{classification_result.get('sub_category')}'")
    logger.info("--- CLAIM CLASSIFIER AGENT FINISHED ---")
    logger.info(SEPARATOR)
    
    return classification_result
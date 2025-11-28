from typing import Any, Tuple, Dict, List
from datetime import datetime, timezone

from models.claim import Claim
from models.collected_data import CollectedDataBundle
import sys
from pathlib import Path

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from logger import get_logger

logger = get_logger(__name__)
SEPARATOR = "-" * 100

async def run(claim: Claim, collected_data: CollectedDataBundle, llm_client: Any) -> Tuple[Dict, List[str]]:
    """
    The Mother Agent synthesizes all collected evidence to create a reasoning strategy.
    It is completely generic and works for any domain (Health, Politics, Finance, etc.).
    """
    logger.info(SEPARATOR)
    logger.info("--- MOTHER LLM AGENT (REASONING ENGINE) BEING CALLED ---")
    
    data_count = len(collected_data.data)
    logger.debug(f"Mother Agent received {data_count} pieces of evidence for analysis.")

    if data_count == 0:
        logger.warning("Mother Agent received NO data. Analysis will be based on claim text only.")

    # Serialize the data into a generic, readable format for the LLM
    # We limit the content length per item to prevent context window overflow
    def sort_key(item):
        ts = item.meta.timestamp
        if isinstance(ts, datetime):
            if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts
        return datetime.min.replace(tzinfo=timezone.utc)

    sorted_items = sorted(collected_data.data, key=sort_key, reverse=True)

    serialized_data = ""
    for i, item in enumerate(sorted_items, 1):
        timestamp = item.meta.timestamp.isoformat() if isinstance(item.meta.timestamp, datetime) else "unknown"
        serialized_data += f"""
        --- Evidence Item {i} ---
        [Source]: {item.meta.source_name}
        [Agent]: {item.meta.agent_name}
        [Timestamp]: {timestamp}
        [URL]: {item.meta.url}
        [Content]:
        {item.content[:2500]}... 
        
        """

    # Call the LLM Client
    # The Generic Prompt is defined inside the LLMClient.analyze_claim_for_mother_agent method
    # in agentic_pipeline.py. This ensures the prompt and the API call stay together.
    analysis_insights, recommended_daughters = await llm_client.analyze_claim_for_mother_agent(
        claim_text=claim.text,
        data=serialized_data
    )
    
    logger.info(f"Mother Agent Analysis Complete.")
    logger.info(f"Identified Topic/Angle: {analysis_insights.get('topic', 'General')}")
    logger.info(f"Recommended Daughter Agent: {recommended_daughters}")
    logger.info("--- MOTHER LLM AGENT FINISHED ---")
    logger.info(SEPARATOR)
    
    return analysis_insights, recommended_daughters
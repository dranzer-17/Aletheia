from typing import Any, Dict, List
from datetime import datetime, timezone

from models.claim import Claim
from models.collected_data import CollectedDataBundle
from models.verification_result import VerificationOutput
import sys
from pathlib import Path

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from logger import get_logger

logger = get_logger(__name__)
SEPARATOR = "-" * 100

async def run(
    claim: Claim, 
    collected_data: CollectedDataBundle, 
    prompt_instructions: Dict, 
    llm_client: Any, 
    domain: str
) -> VerificationOutput:
    
    logger.info(SEPARATOR)
    logger.info(f"--- '{domain.upper()}' DAUGHTER LLM AGENT BEING CALLED ---")
    logger.debug(f"Received instructions: {prompt_instructions}")

    def sort_key(item):
        ts = item.meta.timestamp
        if isinstance(ts, datetime):
            if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts
        return datetime.min.replace(tzinfo=timezone.utc)

    sorted_items = sorted(collected_data.data, key=sort_key, reverse=True)

    relevant_data_content = []
    for item in sorted_items:
        timestamp = item.meta.timestamp.isoformat() if isinstance(item.meta.timestamp, datetime) else "unknown"
        snippet = f"[Source: {item.meta.source_name} | Agent: {item.meta.agent_name} | Timestamp: {timestamp}]\n{item.content}"
        relevant_data_content.append(snippet)

    verification_result = await llm_client.verify_for_daughter_agent(
        claim_text=claim.text,
        relevant_data=relevant_data_content,
        prompt_instructions=prompt_instructions,
        domain=domain
    )
    
    verification_result.claim_id = claim.claim_id
    verification_result.original_claim = claim.text
    
    logger.info(f"--- '{domain.upper()}' DAUGHTER LLM AGENT FINISHED. Verdict: {verification_result.verdict} ---")
    logger.info(SEPARATOR)
    
    return verification_result
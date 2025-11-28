import httpx
from typing import List, Optional, Union
from datetime import datetime

from models.claim import Claim
from models.collected_data import CollectedDataItem, SourceMetaData
import sys
from pathlib import Path

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from logger import get_logger

logger = get_logger(__name__)
SEPARATOR = "-" * 100

def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


async def run(claim: Claim, google_cloud_api_key: str, smart_query: Union[str, List[str]] = None) -> Optional[List[CollectedDataItem]]:
    logger.info(SEPARATOR)
    logger.info("--- GOOGLE FACT CHECK AGENT BEING CALLED ---")
    
    queries = [smart_query] if isinstance(smart_query, str) else (smart_query or [claim.text])
    collected_items: List[CollectedDataItem] = []
    
    async with httpx.AsyncClient() as client:
        for query in queries:
            logger.info(f"Trying Fact Check search with query: '{query}'")
            
            base_url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
            params = {"query": query, "key": google_cloud_api_key, "languageCode": "en"}
            
            try:
                response = await client.get(base_url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                if data and "claims" in data:
                    logger.info(f"Success! Found {len(data['claims'])} fact checks with query '{query}'.")
                    for claim_result in data["claims"]:
                        if "claimReview" in claim_result and claim_result["claimReview"]:
                            for review in claim_result["claimReview"]:
                                publisher = review.get("publisher", {}).get("name", "Unknown Publisher")
                                verdict = review.get("textualRating", "No Verdict")
                                title = review.get("title", "No Title")
                                url = review.get("url", "#")
                                review_date = _parse_datetime(review.get("reviewDate") or review.get("datePublished"))
                                claim_date = _parse_datetime(claim_result.get("claimDate"))
                                timestamp = review_date or claim_date or datetime.utcnow()
                                content = f"Fact Check by: {publisher}\nVerdict: {verdict}\nTitle: {title}\nURL: {url}"
                                collected_items.append(
                                    CollectedDataItem(
                                        content=content,
                                        relevance_score=1.0,
                                        meta=SourceMetaData(
                                            url=url,
                                            timestamp=timestamp,
                                            source_name=f"Fact Check by {publisher}",
                                            agent_name="Google_FactCheck_Agent",
                                        ),
                                    )
                                )
                    
                    break # Stop if we found results
                else:
                    logger.warning(f"No fact checks found for query '{query}'. Trying next...")

            except Exception as e:
                logger.error(f"Fact Check API error for query '{query}': {e}")

    if not collected_items:
        logger.warning("Google Fact Check Agent failed to find reports with any query.")

    logger.info(f"--- GOOGLE FACT CHECK AGENT FINISHED. Returning {len(collected_items)} items. ---")
    logger.info(SEPARATOR)
    return collected_items
from typing import List, Optional, Union
from tavily import TavilyClient
import asyncio

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

# --- DOMAIN KNOWLEDGE BASE ---
DOMAINS_GLOBAL_WIRE = [
    "reuters.com", "bbc.com", "aljazeera.com", "apnews.com", 
    "theguardian.com", "dw.com"
]

DOMAINS_WESTERN_POLITICS = [
    "politico.com", "france24.com", "thehill.com"
]

DOMAINS_INDIA_POLITICS = [
    "ndtv.com", "timesofindia.indiatimes.com", "thehindu.com", 
    "indianexpress.com", "pib.gov.in", "newsonair.gov.in"
]

# Keywords that strongly suggest an Indian context
INDIA_KEYWORDS = [
    "india", "modi", "bjp", "congress", "delhi", "mumbai", 
    "gandhi", "amit shah", "lok sabha", "rajya sabha", "yogi", 
    "aap", "kejriwal", "mamata", "kerala", "bengal", "punjab"
]

async def run(claim: Claim, tavily_api_key: str, smart_query: Optional[Union[str, List[str]]] = None) -> List[CollectedDataItem]:
    """
    Uses Tavily Search to find and extract content from specific political domains.
    """
    logger.info(SEPARATOR)
    logger.info("--- POLITICAL AGENT (TAVILY) BEING CALLED ---")
    
    if not tavily_api_key:
        logger.error("TAVILY_API_KEY is missing.")
        return []

    # Handle smart_query being a list or string
    if isinstance(smart_query, list) and smart_query:
        # Use the first (most specific) query
        query_text = smart_query[0]
    else:
        query_text = smart_query or claim.text

    logger.info(f"Using query: '{query_text}'")

    collected_items: List[CollectedDataItem] = []
    
    # 1. Smart Domain Selection Logic
    claim_text_lower = claim.text.lower()
    target_domains = []
    
    if any(kw in claim_text_lower for kw in INDIA_KEYWORDS):
        logger.info("Context Detection: India-Specific Political Claim.")
        target_domains = DOMAINS_INDIA_POLITICS + DOMAINS_GLOBAL_WIRE
    else:
        logger.info("Context Detection: Global/Western Political Claim.")
        target_domains = DOMAINS_GLOBAL_WIRE + DOMAINS_WESTERN_POLITICS

    logger.info(f"Selected {len(target_domains)} authority domains.")

    try:
        loop = asyncio.get_running_loop()
        
        def tavily_search_sync():
            client = TavilyClient(api_key=tavily_api_key)
            return client.search(
                query=query_text,
                search_depth="advanced",
                include_domains=target_domains,
                max_results=5,
                include_raw_content=False,
                include_images=False
            )

        response = await loop.run_in_executor(None, tavily_search_sync)
        results = response.get("results", [])
        logger.info(f"Tavily found {len(results)} results.")

        for result in results:
            title = result.get("title", "No Title")
            url = result.get("url", "No URL")
            content = result.get("content", "")
            
            if not content: 
                continue

            collected_items.append(
                CollectedDataItem(
                    content=f"Title: {title}\nContent: {content}",
                    relevance_score=result.get("score", 0.9),
                    meta=SourceMetaData(
                        url=url,
                        source_name=title,
                        agent_name="Political_Agent_Tavily"
                    )
                )
            )

    except Exception as e:
        logger.error("An error occurred during the Tavily Political search.", exc_info=True)

    logger.info(f"--- POLITICAL AGENT FINISHED. Returning {len(collected_items)} items. ---")
    logger.info(SEPARATOR)
    return collected_items
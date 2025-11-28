from typing import List, Optional
import asyncio
from importlib import import_module

from models.claim import Claim
import sys
from pathlib import Path

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from logger import get_logger

try:
    GoogleSearch = getattr(import_module("serpapi"), "GoogleSearch")
except (ModuleNotFoundError, AttributeError):
    GoogleSearch = None  # type: ignore[assignment]

logger = get_logger(__name__)
SEPARATOR = "-" * 100

async def run(claim: Claim, serpapi_api_key: str, smart_query: Optional[str] = None) -> List[str]:
    """
    Performs a Google search using SerpApi and returns a list of top URLs.
    """
    logger.info(SEPARATOR)
    logger.info("--- WEB SEARCH AGENT (SERPAPI) BEING CALLED ---")
    
    if GoogleSearch is None:
        logger.error(
            "serpapi.GoogleSearch is unavailable. Install the 'google-search-results' "
            "package or ensure it exposes GoogleSearch."
        )
        logger.info("--- WEB SEARCH AGENT FINISHED. Returning 0 URLs. ---")
        logger.info(SEPARATOR)
        return []
    
    # Validate API key before proceeding
    if not serpapi_api_key:
        logger.error("SERPAPI_API_KEY is not set in environment variables. Please set it in your .env file.")
        logger.info(f"--- WEB SEARCH AGENT FINISHED. Returning 0 URLs. ---")
        logger.info(SEPARATOR)
        return []
    
    final_query = smart_query or claim.text
    logger.info(f"Using smart query for Google Search: '{final_query}'")

    urls_found: List[str] = []
    
    try:
        search_params = {
            "q": final_query,
            "engine": "google",
            "gl": "in",
            "api_key": serpapi_api_key
        }
        
        loop = asyncio.get_running_loop()
        search = await loop.run_in_executor(None, lambda: GoogleSearch(search_params))
        results = search.get_dict()
        
        # --- THIS IS THE CRITICAL FIX ---
        # Check if SerpApi returned an error (e.g., invalid API key, no credits left)
        if "error" in results:
            logger.error(f"SerpApi returned an error: {results['error']}")
            # We return an empty list but the log now clearly states the root cause.
            return []

        organic_results = results.get("organic_results", [])
        if not organic_results:
            logger.warning("SerpApi returned no organic search results.")
        else:
            urls_found = [result['link'] for result in organic_results[:5]]
            logger.info(f"SerpApi found {len(urls_found)} relevant URLs.")

    except Exception as e:
        logger.error("An unhandled error occurred during the SerpApi search operation.", exc_info=True)
    
    logger.info(f"--- WEB SEARCH AGENT FINISHED. Returning {len(urls_found)} URLs. ---")
    logger.info(SEPARATOR)
    return urls_found
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

logger = get_logger(__name__)
SEPARATOR = "-" * 100

try:
    GoogleSearch = getattr(import_module("serpapi"), "GoogleSearch")
except (ModuleNotFoundError, AttributeError):
    GoogleSearch = None  # type: ignore[assignment]

# List of high-authority medical and scientific domains
TRUSTED_HEALTH_DOMAINS = [
    "who.int",                  # World Health Organization
    "cdc.gov",                  # Centers for Disease Control (US)
    "nih.gov",                  # National Institutes of Health
    "pubmed.ncbi.nlm.nih.gov",  # Biomedical Literature Database
    "medlineplus.gov",          # National Library of Medicine
    "mayoclinic.org",           # Top-tier Hospital/Research
    "clevelandclinic.org",      # Top-tier Hospital/Research
    "hopkinsmedicine.org",      # Johns Hopkins
    "webmd.com",                # General verified health info
    "healthline.com",           # Reviewed health articles
    "thelancet.com",            # Medical Journal
    "nejm.org"                  # New England Journal of Medicine
]

async def run(claim: Claim, serpapi_api_key: str, smart_query: Optional[str] = None) -> List[str]:
    """
    Performs a targeted search restricted to trusted health and scientific authorities.
    Returns a list of URLs to be scraped.
    """
    logger.info(SEPARATOR)
    logger.info("--- HEALTH AGENT (SCIENTIFIC & MEDICAL) BEING CALLED ---")
    
    if GoogleSearch is None:
        logger.error(
            "serpapi.GoogleSearch is unavailable. Install the 'google-search-results' "
            "package or ensure it exposes GoogleSearch."
        )
        return []
    
    if not serpapi_api_key:
        logger.error("SERPAPI_API_KEY is missing.")
        return []

    query_text = smart_query or claim.text
    
    # Construct a site-restricted query string
    # Example: (Bournvita cancer) AND (site:who.int OR site:cdc.gov OR ...)
    site_operators = " OR ".join([f"site:{domain}" for domain in TRUSTED_HEALTH_DOMAINS])
    final_query = f"({query_text}) AND ({site_operators})"
    
    logger.info(f"Using targeted health query: '{final_query}'")

    urls_found: List[str] = []
    
    try:
        search_params = {
            "q": final_query,
            "engine": "google",
            "gl": "us", # US setting often yields the best English medical results (CDC/NIH/PubMed)
            "api_key": serpapi_api_key
        }
        
        loop = asyncio.get_running_loop()
        search = await loop.run_in_executor(None, lambda: GoogleSearch(search_params))
        results = search.get_dict()
        
        organic_results = results.get("organic_results", [])
        
        if not organic_results:
            logger.warning("SerpApi returned no results from trusted health domains.")
        else:
            # Take the top 4 most relevant scientific URLs
            urls_found = [result['link'] for result in organic_results[:4]]
            logger.info(f"Found {len(urls_found)} scientific/medical URLs.")
            for url in urls_found:
                logger.debug(f"Health Source Found: {url}")

    except Exception as e:
        logger.error("An error occurred during the Health Agent search.", exc_info=True)
    
    logger.info(f"--- HEALTH AGENT FINISHED. Returning {len(urls_found)} URLs. ---")
    logger.info(SEPARATOR)
    return urls_found
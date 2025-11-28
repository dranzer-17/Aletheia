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

def sanitize_query(query: str) -> str:
    """Sanitize query for GNews API: remove newlines, extra spaces, ensure single line."""
    if not query:
        return ""
    # Remove newlines and carriage returns
    query = query.replace('\n', ' ').replace('\r', ' ')
    # Remove multiple spaces and trim
    query = " ".join(query.split()).strip()
    return query

async def run(claim: Claim, gnews_api_key: str, gnews_api_base_url: str, max_articles: int = 5, smart_query: Union[str, List[str]] = None) -> List[CollectedDataItem]:
    logger.info(SEPARATOR)
    logger.info("--- GNEWS AGENT BEING CALLED ---")
    
    # Handle both single string and list of strings
    queries = [smart_query] if isinstance(smart_query, str) else (smart_query or [claim.text])
    
    # Sanitize all queries to remove newlines and ensure they're URL-safe
    queries = [sanitize_query(q) for q in queries if q]
    
    # If no valid queries after sanitization, use the claim text
    if not queries:
        queries = [sanitize_query(claim.text)]
    
    collected_items: List[CollectedDataItem] = []
    
    async with httpx.AsyncClient() as client:
        for query in queries:
            if not query:  # Skip empty queries
                continue
                
            logger.info(f"Trying GNews search with query: '{query}'")
            
            endpoint = "search"
            url = f"{gnews_api_base_url}{endpoint}"
            params = {"q": query, "lang": "en", "max": max_articles, "apikey": gnews_api_key, "in": "title,description"}

            try:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                if data and data.get("articles"):
                    logger.info(f"Success! Found {len(data['articles'])} articles with query '{query}'.")
                    for article in data["articles"]:
                        title = article.get("title", "No Title")
                        description = article.get("description", "No Description")
                        url = article.get("url", "#")
                        published_at_str = article.get("publishedAt")
                        published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00')) if published_at_str else datetime.now()
                        content = f"Title: {title}\nDescription: {description}\nURL: {url}"
                        collected_items.append(CollectedDataItem(content=content, relevance_score=1.0, meta=SourceMetaData(url=url, timestamp=published_at, source_name=article.get("source", {}).get("name", "GNews"), agent_name="GNews_API_Agent")))
                    
                    # Stop trying queries if we found results
                    break 
                else:
                    logger.warning(f"No articles found for query '{query}'. Trying next...")

            except Exception as e:
                logger.error(f"GNews API error for query '{query}': {e}")
    
    if not collected_items:
        logger.warning("GNews Agent failed to find articles with any query.")

    logger.info(f"--- GNEWS AGENT FINISHED. Returning {len(collected_items)} items. ---")
    logger.info(SEPARATOR)
    return collected_items
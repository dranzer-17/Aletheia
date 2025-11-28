from typing import List
from firecrawl import FirecrawlApp
import asyncio

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

def scrape_url_sync(api_key: str, url: str) -> dict:
    """
    A synchronous helper function to be run in an executor.
    This isolates the blocking call.
    """
    try:
        app = FirecrawlApp(api_key=api_key)
        # The scrape method takes keyword arguments, not a params dict
        result = app.scrape(url=url, only_main_content=True, formats=['markdown'])
        # Convert the Document object to a dict using model_dump (Pydantic v2) or dict() (deprecated but works)
        if hasattr(result, 'model_dump'):
            return result.model_dump()
        elif hasattr(result, 'dict'):
            return result.dict()
        else:
            # Fallback: try to access attributes directly
            return {
                'markdown': getattr(result, 'markdown', ''),
                'metadata': getattr(result, 'metadata', {})
            }
    except Exception as e:
        # Log the error here to capture it immediately
        logger.error(f"Synchronous scrape wrapper failed for URL ({url})", exc_info=e)
        return {} # Return an empty dict on failure

async def run(urls_to_scrape: List[str], firecrawl_api_key: str) -> List[CollectedDataItem]:
    """
    Takes a list of URLs and scrapes their main content using FireCrawl,
    correctly handling the synchronous nature of the library.
    """
    logger.info(SEPARATOR)
    logger.info("--- URL SCRAPER AGENT (FIRECRAWL) BEING CALLED ---")
    logger.info(f"Received {len(urls_to_scrape)} URLs to scrape.")

    collected_items: List[CollectedDataItem] = []
    if not urls_to_scrape:
        logger.warning("No URLs provided to scrape.")
        logger.info(SEPARATOR)
        return collected_items

    loop = asyncio.get_running_loop()
    
    # Create a list of tasks to run in the executor
    tasks = []
    for url in urls_to_scrape:
        # Each task will run the synchronous scrape_url_sync function in a separate thread
        tasks.append(loop.run_in_executor(None, scrape_url_sync, firecrawl_api_key, url))

    # Await all scraping tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, scraped_data in enumerate(results):
        url = urls_to_scrape[i]
        if isinstance(scraped_data, Exception):
            logger.error(f"Error executing scrape task for URL ({url})", exc_info=scraped_data)
            continue

        if scraped_data and 'markdown' in scraped_data:
            content = scraped_data['markdown']
            metadata = scraped_data.get('metadata', {})
            
            collected_items.append(
                CollectedDataItem(
                    content=content,
                    relevance_score=0.8,
                    meta=SourceMetaData(
                        url=url,
                        source_name=metadata.get('title', 'Web Page'),
                        agent_name="URL_Scraper_Agent"
                    )
                )
            )
            logger.info(f"Successfully scraped content from: {url}")
        else:
            logger.warning(f"Failed to extract markdown content from URL: {url}")

    logger.info(f"--- URL SCRAPER AGENT FINISHED. Returning {len(collected_items)} items. ---")
    logger.info(SEPARATOR)
    return collected_items
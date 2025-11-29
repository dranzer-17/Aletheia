import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import importlib.util

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

MISINFO_DIR = BACKEND_ROOT / "misinformation-agent"
if str(MISINFO_DIR) not in sys.path:
    sys.path.insert(0, str(MISINFO_DIR))

from logger import get_logger

# Import from misinformation-agent config
misinfo_config_path = MISINFO_DIR / "config.py"
spec = importlib.util.spec_from_file_location("misinfo_config", misinfo_config_path)
if spec and spec.loader:
    misinfo_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(misinfo_config)
    FIRECRAWL_API_KEY = misinfo_config.APP_CONFIG.get("FIRECRAWL_API_KEY", "")
else:
    FIRECRAWL_API_KEY = ""

# Import agents from misinformation-agent
from agents.data_collection.url_scraper_agent import run as scrape_url

logger = get_logger(__name__)

class URLScraperTool:
    """Tool for scraping content from URLs."""
    
    def __init__(self):
        self.name = "url_scraper"
        self.description = "Scrapes and extracts content from URLs"
    
    async def execute(
        self,
        urls: List[str],
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """Scrape content from URLs."""
        scraped_content = []
        sources = []
        
        for url in urls:
            try:
                if progress_callback:
                    await progress_callback(f"Scraping content from {url}...")
                
                # Scrape URL (scraper expects list of URLs and API key)
                result = await scrape_url([url], FIRECRAWL_API_KEY)
                
                if result:
                    for item in result:
                        # CollectedDataItem has content and meta
                        content = item.content if hasattr(item, 'content') else item.get("content", "")
                        meta = item.meta if hasattr(item, 'meta') else item.get("meta", {})
                        title = meta.source_name if hasattr(meta, 'source_name') else meta.get("source_name", url)
                        item_url = meta.url if hasattr(meta, 'url') else meta.get("url", url)
                        
                        scraped_content.append({
                            "url": item_url,
                            "title": title,
                            "content": content,
                        })
                        
                        sources.append({
                            "title": title,
                            "url": item_url,
                            "snippet": content[:200] + "..." if len(content) > 200 else content,
                            "relevance": 0.9,
                            "agent": "url_scraper",
                        })
                
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                continue
        
        return {
            "success": True,
            "scraped_content": scraped_content,
            "sources": sources,
        }


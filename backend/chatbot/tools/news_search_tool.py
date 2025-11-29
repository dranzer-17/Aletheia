import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

MISINFO_DIR = BACKEND_ROOT / "misinformation-agent"
if str(MISINFO_DIR) not in sys.path:
    sys.path.insert(0, str(MISINFO_DIR))

from logger import get_logger
import importlib.util

# Import from misinformation-agent config
misinfo_config_path = MISINFO_DIR / "config.py"
spec = importlib.util.spec_from_file_location("misinfo_config", misinfo_config_path)
if spec and spec.loader:
    misinfo_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(misinfo_config)
    SERPAPI_API_KEY = misinfo_config.APP_CONFIG.get("SERPAPI_API_KEY", "")
    FIRECRAWL_API_KEY = misinfo_config.APP_CONFIG.get("FIRECRAWL_API_KEY", "")
else:
    SERPAPI_API_KEY = ""
    FIRECRAWL_API_KEY = ""

# Import agents from misinformation-agent
from agents.data_collection.web_search_agent import run as web_search
from agents.data_collection.url_scraper_agent import run as scrape_url
from models.claim import Claim

logger = get_logger(__name__)

class NewsSearchTool:
    """Tool for searching and fetching news."""
    
    def __init__(self):
        # LLM not needed for this tool, but keeping for potential future use
        self.name = "news_search"
        self.description = "Searches and fetches latest news on keywords/topics"
    
    async def execute(
        self,
        query: str,
        max_results: int = 5,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """Search for news and return results."""
        try:
            if progress_callback:
                await progress_callback(f"Searching for news on: {query}...")
            
            # Create claim for search
            claim = Claim(text=query)
            
            # Perform web search (returns list of URLs)
            search_urls = await web_search(claim, SERPAPI_API_KEY)
            
            if progress_callback:
                await progress_callback(f"Found {len(search_urls)} results, fetching content...")
            
            # Scrape top results
            sources = []
            articles = []
            
            for idx, url in enumerate(search_urls[:max_results]):
                if url:
                    try:
                        # Scrape URL
                        scraped = await scrape_url([url], FIRECRAWL_API_KEY)
                        
                        if scraped:
                            item = scraped[0]
                            content = item.content if hasattr(item, 'content') else item.get("content", "")
                            meta = item.meta if hasattr(item, 'meta') else item.get("meta", {})
                            title = meta.source_name if hasattr(meta, 'source_name') else meta.get("source_name", url)
                            
                            articles.append({
                                "title": title,
                                "url": url,
                                "content": content,
                            })
                            
                            sources.append({
                                "title": title,
                                "url": url,
                                "snippet": content[:200] + "..." if len(content) > 200 else content,
                                "relevance": 0.9 - (idx * 0.1),
                                "agent": "news_search",
                            })
                    except Exception as e:
                        logger.error(f"Error scraping {url}: {e}")
                        # Still add URL even if scraping fails
                        sources.append({
                            "title": url,
                            "url": url,
                            "snippet": "",
                            "relevance": 0.8 - (idx * 0.1),
                            "agent": "news_search",
                        })
            
            # Format response
            response_html = self._format_response(query, articles)
            
            return {
                "success": True,
                "response": response_html,
                "sources": sources,
                "metadata": {
                    "query": query,
                    "results_count": len(sources),
                },
            }
            
        except Exception as e:
            logger.error(f"News search tool error: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"<p>Error searching for news: {str(e)}</p>",
                "sources": [],
                "metadata": {},
            }
    
    def _format_response(self, query: str, articles: List[Dict]) -> str:
        """Format response as HTML."""
        html = f"""
        <div>
            <h3 style="margin-bottom: 12px;">Latest News on: {query}</h3>
            <p style="margin-bottom: 12px;">Found {len(articles)} articles:</p>
            <ul style="margin-left: 20px;">
        """
        
        for idx, article in enumerate(articles):
            html += f"""
                <li style="margin-bottom: 8px;">
                    <strong>{article['title']}</strong>
                    <br/>
                    <span style="color: #666; font-size: 0.9em;">{article['content'][:150]}...</span>
                </li>
            """
        
        html += """
            </ul>
        </div>
        """
        return html.strip()


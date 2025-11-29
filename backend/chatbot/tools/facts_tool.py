import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, List

import wikipedia

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from logger import get_logger
import importlib.util

MISINFO_DIR = BACKEND_ROOT / "misinformation-agent"
if str(MISINFO_DIR) not in sys.path:
    sys.path.insert(0, str(MISINFO_DIR))

misinfo_config_path = MISINFO_DIR / "config.py"
spec = importlib.util.spec_from_file_location("misinfo_config", misinfo_config_path)
if spec and spec.loader:
    misinfo_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(misinfo_config)
    APP_CONFIG = misinfo_config.APP_CONFIG
else:
    APP_CONFIG = {}

from models.claim import Claim  # type: ignore
from agents.data_collection import web_search_agent  # type: ignore


logger = get_logger(__name__)


class FactsLookupTool:
    """Tool for quick factual lookups using Wikipedia and Google (SerpApi)."""

    def __init__(self):
        self.name = "facts_lookup"
        self.description = "Fetches factual answers from Wikipedia and Google search snippets"
        self.serpapi_api_key = APP_CONFIG.get("SERPAPI_API_KEY")

    async def execute(self, query: str) -> Dict[str, Any]:
        try:
            wikipedia_summary = await self._fetch_wikipedia_summary(query)
            search_results = await self._fetch_search_results(query)

            response_html = self._format_response(query, wikipedia_summary, search_results)

            sources: List[Dict[str, str]] = []
            if wikipedia_summary.get("url"):
                sources.append(
                    {
                        "title": wikipedia_summary["title"],
                        "url": wikipedia_summary["url"],
                        "snippet": wikipedia_summary["summary"],
                        "agent": "Wikipedia",
                    }
                )

            for result in search_results:
                sources.append(
                    {
                        "title": result.get("title", "Web Result"),
                        "url": result.get("url", ""),
                        "snippet": result.get("snippet", ""),
                        "agent": "Google Search",
                    }
                )

            return {
                "success": True,
                "response": response_html,
                "sources": sources,
                "metadata": {
                    "wikipedia": wikipedia_summary,
                    "search_results": search_results,
                },
            }
        except Exception as e:
            logger.error(f"Facts lookup failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"<p>Unable to fetch factual details: {str(e)}</p>",
                "sources": [],
                "metadata": {},
            }

    async def _fetch_wikipedia_summary(self, query: str) -> Dict[str, str]:
        summary_data: Dict[str, str] = {}
        loop = asyncio.get_running_loop()

        try:
            page_title = await loop.run_in_executor(None, lambda: wikipedia.search(query, results=1))
            if not page_title:
                return summary_data

            title = page_title[0]

            summary = await loop.run_in_executor(
                None, lambda: wikipedia.summary(title, sentences=3, auto_suggest=False)
            )
            url = await loop.run_in_executor(
                None, lambda: wikipedia.page(title, auto_suggest=False).url
            )

            summary_data = {
                "title": title,
                "summary": summary,
                "url": url,
            }
        except Exception as e:
            logger.warning(f"Wikipedia lookup failed for '{query}': {e}")

        return summary_data

    async def _fetch_search_results(self, query: str) -> List[Dict[str, str]]:
        if not self.serpapi_api_key:
            return []

        try:
            claim = Claim(text=query)
            urls = await web_search_agent.run(
                claim=claim,
                serpapi_api_key=self.serpapi_api_key,
                smart_query=query,
            )
            return [
                {
                    "title": url,
                    "url": url,
                    "snippet": "",
                }
                for url in urls[:3]
            ]
        except Exception as e:
            logger.warning(f"Google search failed for '{query}': {e}")
            return []

    def _format_response(
        self,
        query: str,
        wikipedia_summary: Dict[str, str],
        search_results: List[Dict[str, str]],
    ) -> str:
        sections = [f"<h3>Quick Facts: {query}</h3>"]

        if wikipedia_summary:
            sections.append(
                f"""
                <div>
                    <h4>Wikipedia</h4>
                    <p><strong>{wikipedia_summary.get('title')}</strong></p>
                    <p>{wikipedia_summary.get('summary')}</p>
                    <p><a href="{wikipedia_summary.get('url')}" target="_blank">View on Wikipedia</a></p>
                </div>
                """
            )
        else:
            sections.append("<p>No Wikipedia summary available.</p>")

        if search_results:
            sections.append("<h4>Additional Web References</h4><ul>")
            for result in search_results:
                sections.append(
                    f"""<li>
                        <a href="{result.get('url', '#')}" target="_blank">{result.get('title', 'Web Result')}</a>
                        </li>"""
                )
            sections.append("</ul>")

        return "\n".join(sections)


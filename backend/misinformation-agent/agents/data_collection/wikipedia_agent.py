import wikipedia
from typing import List
from models.collected_data import CollectedDataItem, SourceMetaData
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

async def run(claim: Claim) -> List[CollectedDataItem]:
    logger.info(SEPARATOR)
    logger.info("--- WIKIPEDIA AGENT BEING CALLED ---")
    
    collected_items: List[CollectedDataItem] = []
    # Use extracted keywords if available, else the claim text
    search_terms = claim.keywords if claim.keywords else [claim.text]
    # Limit to first 2 keywords
    target_terms = search_terms[:2]
    
    logger.info(f"Searching Wikipedia for terms: {target_terms}")

    for term in target_terms:
        try:
            # Search for the page
            search_results = wikipedia.search(term)
            if not search_results:
                logger.warning(f"No Wikipedia results for '{term}'")
                continue
            
            # Pick the first result
            page_title = search_results[0]
            
            try:
                # Get summary (auto_suggest=False avoids some weird redirects)
                summary = wikipedia.summary(page_title, sentences=5, auto_suggest=False)
                try:
                    url = wikipedia.page(page_title, auto_suggest=False).url
                except:
                    url = f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
                
                collected_items.append(
                    CollectedDataItem(
                        content=f"Wikipedia Summary for '{page_title}':\n{summary}",
                        relevance_score=0.9,
                        meta=SourceMetaData(
                            url=url,
                            source_name="Wikipedia",
                            agent_name="Wikipedia_Agent"
                        )
                    )
                )
                logger.info(f"Found Wikipedia page: '{page_title}'")

            except wikipedia.exceptions.DisambiguationError as e:
                # If ambiguous, try the first option in the disambiguation list
                if e.options:
                    first_option = e.options[0]
                    logger.info(f"Term '{term}' is ambiguous. Trying first option: '{first_option}'")
                    try:
                        summary = wikipedia.summary(first_option, sentences=5, auto_suggest=False)
                        url = f"https://en.wikipedia.org/wiki/{first_option.replace(' ', '_')}"
                         
                        collected_items.append(
                            CollectedDataItem(
                                content=f"Wikipedia Summary for '{first_option}':\n{summary}",
                                relevance_score=0.85,
                                meta=SourceMetaData(
                                    url=url,
                                    source_name="Wikipedia",
                                    agent_name="Wikipedia_Agent"
                                )
                            )
                        )
                    except:
                        logger.warning(f"Failed to fetch disambiguated page '{first_option}'")

            except wikipedia.exceptions.PageError:
                logger.warning(f"Wikipedia page not found for '{page_title}'.")

        except Exception as e:
            logger.warning(f"Wikipedia lookup failed for term '{term}': {e}")

    logger.info(f"--- WIKIPEDIA AGENT FINISHED. Returning {len(collected_items)} items. ---")
    logger.info(SEPARATOR)
    return collected_items
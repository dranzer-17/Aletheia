import yfinance as yf
from tavily import TavilyClient
import asyncio
from typing import List, Any, Optional, Union

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

# Financial News Domains
FINANCE_DOMAINS = [
    "bloomberg.com", "wsj.com", "ft.com", "cnbc.com", "reuters.com",
    "economictimes.indiatimes.com", "moneycontrol.com", "livemint.com",
    "business-standard.com", "investopedia.com"
]

async def run(claim: Claim, llm_client: Any, tavily_api_key: str, smart_query: Optional[Union[str, List[str]]] = None) -> List[CollectedDataItem]:
    logger.info(SEPARATOR)
    logger.info("--- FINANCE AGENT (MARKET DATA + NEWS) BEING CALLED ---")
    
    collected_items: List[CollectedDataItem] = []

    # Determine text to use for analysis
    if isinstance(smart_query, list) and smart_query:
        # Use the "Broad" query (usually 2nd or just use 1st) for ticker extraction context
        query_text = smart_query[0]
    else:
        query_text = smart_query or claim.text
    
    # --- PART 1: Real-Time Market Data (YFinance) ---
    ticker = await llm_client.extract_ticker_symbol(query_text)
    
    if ticker:
        logger.info(f"LLM identified ticker: '{ticker}'. Fetching market data...")
        try:
            stock = yf.Ticker(ticker)
            
            # Try to get price data with multiple fallbacks
            price = None
            currency = "USD"
            
            # Method 1: Try fast_info
            try:
                if hasattr(stock, 'fast_info') and stock.fast_info:
                    price = stock.fast_info.last_price
                    if hasattr(stock.fast_info, 'currency'):
                        currency = stock.fast_info.currency or "USD"
            except Exception as e:
                logger.debug(f"fast_info failed: {e}")
            
            # Method 2: Try history (last close price)
            if price is None:
                try:
                    hist = stock.history(period="1d", interval="1m")
                    if not hist.empty:
                        price = float(hist['Close'].iloc[-1])
                        logger.info(f"Got price from history: {price}")
                except Exception as e:
                    logger.debug(f"history failed: {e}")
            
            # Method 3: Try info dict
            if price is None:
                try:
                    info = stock.info
                    if info and 'regularMarketPrice' in info:
                        price = info.get('regularMarketPrice')
                    elif info and 'currentPrice' in info:
                        price = info.get('currentPrice')
                    if info and 'currency' in info:
                        currency = info.get('currency', 'USD')
                except Exception as e:
                    logger.debug(f"info dict failed: {e}")
            
            # Get additional info
            short_name = ticker
            sector = 'N/A'
            news_summary = ""
            
            try:
                info = stock.info
                if info:
                    short_name = info.get('shortName') or info.get('longName') or ticker
                    sector = info.get('sector') or info.get('industry') or 'N/A'
                    
                    # Get news
                    try:
                        news_items = stock.news[:2] if stock.news else []
                        if news_items:
                            news_summary = "\n".join([f"- {n.get('title', 'N/A')} ({n.get('publisher', 'N/A')})" for n in news_items])
                    except Exception as e:
                        logger.debug(f"News fetch failed: {e}")
            except Exception as e:
                logger.debug(f"Info fetch failed: {e}")
            
            if price is not None:
                content = (
                    f"*** MARKET DATA FOR {short_name} ({ticker}) ***\n"
                    f"Current Price: {price} {currency}\n"
                    f"Sector: {sector}\n"
                )
                if news_summary:
                    content += f"Recent Headlines:\n{news_summary}"
                
                collected_items.append(
                    CollectedDataItem(
                        content=content,
                        relevance_score=1.0,
                        meta=SourceMetaData(
                            url=f"https://finance.yahoo.com/quote/{ticker}",
                            source_name="Yahoo Finance API",
                            agent_name="Finance_Agent"
                        )
                    )
                )
                logger.info(f"Successfully fetched data for {ticker}: Price = {price} {currency}")
            else:
                logger.warning(f"Could not fetch price data for '{ticker}' - all methods failed")
        except Exception as e:
            logger.warning(f"Failed to fetch YFinance data for '{ticker}': {e}", exc_info=True)
    else:
        logger.info("No specific ticker symbol identified in the claim.")

    # --- PART 2: Financial News Search (Tavily) ---
    if tavily_api_key:
        logger.info("Searching authority financial domains via Tavily...")
        try:
            loop = asyncio.get_running_loop()
            def tavily_search():
                return TavilyClient(api_key=tavily_api_key).search(
                    query=query_text,
                    search_depth="advanced",
                    include_domains=FINANCE_DOMAINS,
                    max_results=4
                )
            
            response = await loop.run_in_executor(None, tavily_search)
            results = response.get("results", [])
            logger.info(f"Tavily found {len(results)} financial news articles.")

            for result in results:
                collected_items.append(
                    CollectedDataItem(
                        content=f"Title: {result.get('title')}\nContent: {result.get('content')}",
                        relevance_score=0.9,
                        meta=SourceMetaData(
                            url=result.get("url", ""),
                            source_name=result.get("title", "Financial News"),
                            agent_name="Finance_Agent_Tavily"
                        )
                    )
                )
        except Exception as e:
            logger.error("Tavily Financial Search failed.", exc_info=True)

    logger.info(f"--- FINANCE AGENT FINISHED. Returning {len(collected_items)} items. ---")
    logger.info(SEPARATOR)
    return collected_items
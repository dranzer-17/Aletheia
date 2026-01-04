import asyncio
from typing import List, TypedDict, Optional, Dict, Any, Callable, Awaitable
from functools import partial
import pprint
from uuid import UUID, uuid4
import sys
from pathlib import Path
import re

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from langgraph.graph import StateGraph, END

from models.claim import Claim
from models.collected_data import CollectedDataBundle, CollectedDataItem
from models.verification_result import VerificationOutput
from models.media import MediaItem
from logger import get_logger
from data_manager import save_json

from agents.pre_processing.claim_classifier_agent import run as run_classifier_agent
from agents.pre_processing import longform_summarizer_agent
from agents.data_collection import gnews_api_agent
from agents.data_collection import google_fact_check_agent
from agents.data_collection import web_search_agent
from agents.data_collection import url_scraper_agent
from agents.data_collection import political_agent
from agents.data_collection import finance_agent
from agents.data_collection import wikipedia_agent
from agents.data_collection import health_agent

from agents.verification import llm_mother_agent
from agents.verification import llm_daughter_agent
from agents.post_processing import score_calculator_agent # <-- NEW IMPORT
from agents.post_processing import sentiment_agent
from agents.post_processing import emotion_agent
from agents.media import image_claim_agent

logger = get_logger(__name__)

class GraphState(TypedDict):
    raw_claim_text: str
    claim: Claim
    media_items: List[MediaItem]
    media_claims: List[Dict[str, Any]]
    classification_result: Dict[str, Any]
    urls_to_scrape: List[str]
    manual_urls: List[str]
    collected_data: CollectedDataBundle
    longform_summaries: List[Dict[str, Any]]
    mother_agent_analysis: Optional[Dict[str, Any]]
    daughter_agent_results: Dict[str, VerificationOutput]
    final_verification_output: Optional[VerificationOutput]
    sentiment_result: Optional[Dict[str, Any]]
    emotion_result: Optional[Dict[str, Any]]
    errors: List[str]
    agents_used: List[str]
    use_web_search: bool
    forced_agents: List[str]


async def report_stage(
    callback: Optional[Callable[[str], Awaitable[None]]], message: str
):
    if callback:
        await callback(message)


async def media_claim_processing_node(
    state: GraphState, llm_client: Any, status_callback=None
) -> Dict[str, Any]:
    media_items = state.get("media_items", [])
    if not media_items:
        return {}

    await report_stage(status_callback, "Analyzing media attachments")

    claim = state["claim"]
    current_bundle = state.get("collected_data") or CollectedDataBundle(
        data=[], errors=[]
    )
    agents_used = state.get("agents_used", [])

    result = await image_claim_agent.run(
        claim=claim,
        media_items=media_items,
        llm_client=llm_client,
    )

    extracted_claims = result.get("extracted_claims", [])
    primary_claim = result.get("primary_claim")
    collected_items = result.get("collected_items", [])
    analysis_errors = result.get("errors", [])

    if collected_items:
        current_bundle.data.extend(collected_items)

    if analysis_errors:
        current_bundle.errors.extend(analysis_errors)

    agents_used.append(image_claim_agent.run.__module__)
    save_json("image_claim_data.json", result)

    if primary_claim:
        if state["raw_claim_text"]:
            claim.context = state["raw_claim_text"]
        state["raw_claim_text"] = primary_claim
        claim.text = primary_claim

    media_claims = list(state.get("media_claims", []))
    if extracted_claims:
        media_claims.extend(extracted_claims)

    return {
        "claim": claim,
        "collected_data": current_bundle,
        "agents_used": agents_used,
        "media_claims": media_claims,
    }

# --- Triggers ---
POLITICAL_TRIGGERS = ["government", "minister", "president", "senate", "parliament", "law", "bill", "act", "election", "vote", "party", "congress", "bjp", "democrat", "republican", "modi", "biden", "trump", "putin", "opposition"]
HEALTH_TRIGGERS = ["cancer", "disease", "virus", "health", "doctor", "vaccine", "who", "cdc", "nutrition"]
FINANCE_TRIGGERS = ["stock", "market", "price", "tax", "budget", "economy", "crypto", "bitcoin", "rupee", "dollar", "bank"]
URL_EXTRACT_PATTERN = r"https?://[^\s]+"
LONG_TEXT_WORD_THRESHOLD = 25

# --- Graph Nodes ---

async def claim_classifier_node(state: GraphState, llm_client: Any, status_callback=None) -> Dict[str, Any]:
    claim = state['claim']
    await report_stage(status_callback, "Classifying claim")
    classification = await run_classifier_agent(claim.text, llm_client)
    save_json("claim_classification.json", classification)
    if state.get('claim'):
        state['claim'].keywords = classification.get('keywords', [])
    return {"classification_result": classification}

FORCED_AGENT_MAP = {
    "wikipedia": "wikipedia",
    "political": "political",
    "health": "health",
    "finance": "finance",
}


async def independent_data_collection_node(state: GraphState, config_args: Dict[str, Any], llm_client: Any, status_callback=None) -> Dict[str, Any]:
    logger.info("-" * 100)
    logger.info("--- Entering Independent Data Collection Node ---")
    await report_stage(status_callback, "Collecting evidence")
    claim = state["claim"]
    use_web_search = state["use_web_search"]
    classification = state["classification_result"]
    category = classification.get("category", "General").strip()
    text_lower = claim.text.lower()
    
    smart_query = await llm_client.generate_search_query(claim.text)
    
    # 1. Core Agents
    agents_to_run = {
        "gnews": (gnews_api_agent.run, {
            "claim": claim, "smart_query": smart_query, 
            "gnews_api_key": config_args.get("GNEWS_API_KEY"),
            "gnews_api_base_url": config_args.get("GNEWS_API_BASE_URL")
        }),
        "fact_check": (google_fact_check_agent.run, {
            "claim": claim, "smart_query": smart_query, 
            "google_cloud_api_key": config_args.get("GOOGLE_CLOUD_API_KEY")
        }),
    }

    if use_web_search:
        logger.info("Web search is ENABLED.")
        agents_to_run["web_search"] = (web_search_agent.run, {
            "claim": claim, "smart_query": smart_query, 
            "serpapi_api_key": config_args.get("SERPAPI_API_KEY")
        })

    logger.info(f"Checking specialist agents for category: '{category}'")
    
    is_politics = (category == 'Politics') or any(t in text_lower for t in POLITICAL_TRIGGERS)
    if is_politics:
        logger.info("Activating Political Agent.")
        agents_to_run["political"] = (political_agent.run, {
            "claim": claim, "smart_query": smart_query,
            "tavily_api_key": config_args.get("TAVILY_API_KEY")
        })

    is_finance = (category == 'Finance') or any(t in text_lower for t in FINANCE_TRIGGERS)
    if is_finance:
        logger.info("Activating Finance Agent.")
        agents_to_run["finance"] = (finance_agent.run, {
            "claim": claim, "smart_query": smart_query,
            "llm_client": llm_client, "tavily_api_key": config_args.get("TAVILY_API_KEY")
        })

    is_health = (category == 'Health') or any(t in text_lower for t in HEALTH_TRIGGERS)
    if is_health:
        logger.info("Activating Health Agent.")
        agents_to_run["health"] = (health_agent.run, {
            "claim": claim, "smart_query": smart_query,
            "serpapi_api_key": config_args.get("SERPAPI_API_KEY")
        })

    if category in ['Science', 'Education', 'General'] and not (is_politics or is_finance or is_health):
        logger.info("Activating Wikipedia Agent.")
        agents_to_run["wikipedia"] = (wikipedia_agent.run, {"claim": claim})

    # Forced agents (ensure they are present)
    forced = state.get("forced_agents", [])
    for forced_key in forced:
        mapped = FORCED_AGENT_MAP.get(forced_key)
        if not mapped or mapped in agents_to_run:
            continue

        if mapped == "wikipedia":
            agents_to_run[mapped] = (wikipedia_agent.run, {"claim": claim})
        elif mapped == "political":
            agents_to_run[mapped] = (
                political_agent.run,
                {
                    "claim": claim,
                    "smart_query": smart_query,
                    "tavily_api_key": config_args.get("TAVILY_API_KEY"),
                },
            )
        elif mapped == "health":
            agents_to_run[mapped] = (
                health_agent.run,
                {
                    "claim": claim,
                    "smart_query": smart_query,
                    "serpapi_api_key": config_args.get("SERPAPI_API_KEY"),
                },
            )
        elif mapped == "finance":
            agents_to_run[mapped] = (
                finance_agent.run,
                {
                    "claim": claim,
                    "smart_query": smart_query,
                    "llm_client": llm_client,
                    "tavily_api_key": config_args.get("TAVILY_API_KEY"),
                },
            )

    # --- Execution ---
    tasks = [func(**args) for func, args in agents_to_run.values()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_collected_items, collection_errors, successful_agents = [], [], []
    urls_from_search = []
    
    result_map = dict(zip(agents_to_run.keys(), results))

    for agent_key, res in result_map.items():
        agent_module = agents_to_run[agent_key][0].__module__
        if isinstance(res, Exception):
            collection_errors.append(f"{agent_module}: {res}")
            logger.error(f"Agent {agent_module} failed.", exc_info=res)
            continue
            
        successful_agents.append(agent_module)
        save_json(f"{agent_key}_data.json", res)

        if isinstance(res, list):
            if not res: continue
            if isinstance(res[0], str):
                urls_from_search.extend(res)
            else:
                all_collected_items.extend(res)

    bundle = CollectedDataBundle(data=all_collected_items, errors=collection_errors)
    logger.info("--- Exiting Independent Data Collection Node ---")
    return {"collected_data": bundle, "agents_used": successful_agents, "urls_to_scrape": urls_from_search}

async def url_scraper_node(state: GraphState, config_args: Dict[str, Any], status_callback=None) -> Dict[str, Any]:
    logger.info("-" * 100)
    logger.info("--- Entering URL Scraper Node ---")
    await report_stage(status_callback, "Scraping supplemental URLs")
    urls = list(set(state.get("urls_to_scrape", [])))
    current_bundle = state.get("collected_data", CollectedDataBundle(data=[], errors=[]))
    agents_used = state.get("agents_used", [])

    if not urls:
        logger.warning("No URLs to scrape.")
        return {}

    scraped_items = await url_scraper_agent.run(urls, config_args.get("TAVILY_API_KEY"))
    save_json("scraped_content_data.json", scraped_items)
    if scraped_items:
        agents_used.append(url_scraper_agent.run.__module__)
        current_bundle.data.extend(scraped_items)
    
    logger.info("--- Exiting URL Scraper Node ---")
    return {"collected_data": current_bundle, "agents_used": agents_used}


async def content_enrichment_node(
    state: GraphState,
    llm_client: Any,
    config_args: Dict[str, Any],
    status_callback=None,
) -> Dict[str, Any]:
    claim = state["claim"]
    raw_text = state.get("raw_claim_text", "")
    await report_stage(status_callback, "Enriching claim content")

    bundle = state.get("collected_data") or CollectedDataBundle(data=[], errors=[])
    agents_used = state.get("agents_used", [])
    manual_urls = state.get("manual_urls", [])

    if not manual_urls and raw_text:
        manual_urls = list(
            {
                match.group(0).rstrip(".,)")
                for match in re.finditer(URL_EXTRACT_PATTERN, raw_text)
            }
        )

    scraped_items: List[CollectedDataItem] = []
    if manual_urls:
        scraped_items = await url_scraper_agent.run(
            manual_urls,
            config_args.get("TAVILY_API_KEY"),
        )
        if scraped_items:
            bundle.data.extend(scraped_items)
            if url_scraper_agent.run.__module__ not in agents_used:
                agents_used.append(url_scraper_agent.run.__module__)

    async def summarize_source(
        text: str,
        source_name: str,
        source_url: str,
    ) -> Optional[Dict[str, Any]]:
        if not text or len(text.split()) < LONG_TEXT_WORD_THRESHOLD:
            return None

        summary_payload = await longform_summarizer_agent.run(
            text=text,
            source_name=source_name or "Source",
            source_url=source_url or "about:blank",
            llm_client=llm_client,
        )

        if summary_payload.get("collected_item"):
            bundle.data.append(summary_payload["collected_item"])
            if longform_summarizer_agent.run.__module__ not in agents_used:
                agents_used.append(longform_summarizer_agent.run.__module__)

        return summary_payload.get("summary")

    longform_summaries = state.get("longform_summaries", [])

    summary_from_claim = await summarize_source(
        raw_text,
        source_name="User Claim",
        source_url="about:claim",
    )
    if summary_from_claim:
        longform_summaries.append(summary_from_claim)

    for item in scraped_items:
        summary = await summarize_source(
            item.content,
            source_name=item.meta.source_name,
            source_url=item.meta.url,
        )
        if summary:
            longform_summaries.append(summary)

    return {
        "collected_data": bundle,
        "agents_used": agents_used,
        "manual_urls": manual_urls,
        "longform_summaries": longform_summaries,
    }

async def llm_mother_agent_node(state: GraphState, llm_client: Any, status_callback=None) -> Dict[str, Any]:
    claim, collected_data = state["claim"], state["collected_data"]
    await report_stage(status_callback, "Synthesizing evidence (Mother agent)")
    analysis_insights, recommended_daughters = await llm_mother_agent.run(claim, collected_data, llm_client)
    save_json("mother_agent_analysis.json", {"insights": analysis_insights, "recommended_daughters": recommended_daughters})
    return {"mother_agent_analysis": {"insights": analysis_insights, "recommended_daughters": recommended_daughters}}

async def llm_daughter_general_node(state: GraphState, llm_client: Any, status_callback=None) -> Dict[str, Any]:
    claim, collected_data, mother_analysis = state["claim"], state["collected_data"], state["mother_agent_analysis"]
    await report_stage(status_callback, "Verifying claim (Daughter agent)")
    result = await llm_daughter_agent.run(claim=claim, collected_data=collected_data, prompt_instructions=mother_analysis.get("insights", {}), llm_client=llm_client, domain="general")
    return {"daughter_agent_results": {"general": result}}

# --- NEW: SCORE CALCULATOR NODE ---
async def score_calculator_node(state: GraphState, llm_client: Any, status_callback=None) -> Dict[str, Any]:
    logger.info("-" * 100)
    logger.info("--- Entering Score Calculator Node ---")
    await report_stage(status_callback, "Calculating final confidence")
    
    claim = state["claim"]
    collected_data = state["collected_data"]
    daughter_results = state["daughter_agent_results"]
    agents_used = state["agents_used"]
    
    prelim_result = list(daughter_results.values())[0] if daughter_results else None
    
    if prelim_result:
        # Call the Score Calculator Agent
        final_result = await score_calculator_agent.run(
            claim=claim,
            collected_data=collected_data,
            verification_result=prelim_result,
            # No LLM client passed because we use local embeddings
            agents_used=agents_used
        )
        
        if collected_data:
            final_result.sources_used = [item.meta for item in collected_data.data]
            
        save_json("final_verdict.json", final_result)
        return {"final_verification_output": final_result}
    
    return {}

# --- SENTIMENT ANALYSIS NODE ---
async def sentiment_analysis_node(state: GraphState, llm_client: Any, status_callback=None) -> Dict[str, Any]:
    logger.info("-" * 100)
    logger.info("--- Entering Sentiment Analysis Node ---")
    await report_stage(status_callback, "Analyzing sentiment")
    
    claim = state["claim"]
    
    try:
        sentiment_result = await sentiment_agent.run(claim, llm_client)
        save_json("sentiment_analysis.json", sentiment_result)
        return {"sentiment_result": sentiment_result}
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}", exc_info=True)
        return {"sentiment_result": None}

# --- EMOTION ANALYSIS NODE ---
async def emotion_analysis_node(state: GraphState, llm_client: Any, status_callback=None) -> Dict[str, Any]:
    logger.info("-" * 100)
    logger.info("--- Entering Emotion Analysis Node ---")
    await report_stage(status_callback, "Analyzing emotions")
    
    claim = state["claim"]
    
    try:
        emotion_result = await emotion_agent.run(claim, llm_client)
        save_json("emotion_analysis.json", emotion_result)
        return {"emotion_result": emotion_result}
    except Exception as e:
        logger.error(f"Emotion analysis failed: {e}", exc_info=True)
        return {"emotion_result": None}

def route_to_daughter(state: GraphState) -> str:
    return "llm_daughter_general"

class ClaimOrchestratorAgent:
    def __init__(
        self,
        llm_client: Any,
        config_args: Dict[str, Any],
        use_web_search: bool,
        forced_agents: List[str],
        media_items: List[MediaItem],
        status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self.llm_client = llm_client
        self.config_args = config_args
        self.use_web_search = use_web_search
        self.forced_agents = forced_agents
        self.media_items = media_items
        self.status_callback = status_callback
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
        logger.info("ClaimOrchestratorAgent initialized.")

    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(GraphState)
        
        classifier_with_client = partial(
            claim_classifier_node,
            llm_client=self.llm_client,
            status_callback=self.status_callback,
        )
        media_processing_with_client = partial(
            media_claim_processing_node,
            llm_client=self.llm_client,
            status_callback=self.status_callback,
        )
        independent_collection_with_deps = partial(
            independent_data_collection_node,
            config_args=self.config_args,
            llm_client=self.llm_client,
            status_callback=self.status_callback,
        )
        scraper_with_config = partial(
            url_scraper_node,
            config_args=self.config_args,
            status_callback=self.status_callback,
        )
        enrichment_with_client = partial(
            content_enrichment_node,
            llm_client=self.llm_client,
            config_args=self.config_args,
            status_callback=self.status_callback,
        )
        mother_with_client = partial(
            llm_mother_agent_node,
            llm_client=self.llm_client,
            status_callback=self.status_callback,
        )
        daughter_with_client = partial(
            llm_daughter_general_node,
            llm_client=self.llm_client,
            status_callback=self.status_callback,
        )
        # Score Calculator node
        score_calculator_with_client = partial(
            score_calculator_node,
            llm_client=self.llm_client,
            status_callback=self.status_callback,
        )
        # Sentiment and Emotion nodes (use LLM client)
        sentiment_with_client = partial(
            sentiment_analysis_node,
            llm_client=self.llm_client,
            status_callback=self.status_callback,
        )
        emotion_with_client = partial(
            emotion_analysis_node,
            llm_client=self.llm_client,
            status_callback=self.status_callback,
        )

        workflow.add_node("media_claim_processing", media_processing_with_client)
        workflow.add_node("claim_classifier", classifier_with_client)
        workflow.add_node("independent_data_collection", independent_collection_with_deps)
        workflow.add_node("url_scraper", scraper_with_config)
        workflow.add_node("content_enrichment", enrichment_with_client)
        workflow.add_node("llm_mother_agent", mother_with_client)
        workflow.add_node("llm_daughter_general", daughter_with_client)
        workflow.add_node("score_calculator", score_calculator_with_client)
        workflow.add_node("sentiment_analysis", sentiment_with_client)
        workflow.add_node("emotion_analysis", emotion_with_client)
        
        workflow.set_entry_point("media_claim_processing")
        workflow.add_edge("media_claim_processing", "claim_classifier")
        workflow.add_edge("claim_classifier", "independent_data_collection")
        workflow.add_edge("independent_data_collection", "url_scraper")
        workflow.add_edge("url_scraper", "content_enrichment")
        workflow.add_edge("content_enrichment", "llm_mother_agent")
        workflow.add_conditional_edges("llm_mother_agent", route_to_daughter)
        workflow.add_edge("llm_daughter_general", "score_calculator")
        # Run sentiment and emotion analysis sequentially after score calculator
        workflow.add_edge("score_calculator", "sentiment_analysis")
        workflow.add_edge("sentiment_analysis", "emotion_analysis")
        workflow.add_edge("emotion_analysis", END)
        
        return workflow

    async def run_workflow(self, raw_claim_text: str, external_claim_id=None) -> GraphState:
        claim_identifier = UUID(str(external_claim_id)) if external_claim_id else uuid4()
        claim_obj = Claim(text=raw_claim_text, claim_id=claim_identifier)
        initial_graph_state = {
            "raw_claim_text": raw_claim_text,
            "claim": claim_obj,
            "media_items": self.media_items,
            "media_claims": [],
            "classification_result": None,
            "urls_to_scrape": [],
            "manual_urls": [],
            "collected_data": None,
            "longform_summaries": [],
            "mother_agent_analysis": None,
            "daughter_agent_results": {},
            "final_verification_output": None,
            "errors": [],
            "agents_used": [],
            "use_web_search": self.use_web_search,
            "forced_agents": self.forced_agents,
        }
        final_state_full = await self.app.ainvoke(initial_graph_state)
        return final_state_full
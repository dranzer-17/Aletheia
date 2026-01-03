import asyncio
from uuid import uuid4
from typing import List, Dict, Any, Tuple, Optional, Union, Callable, Awaitable
import sys
import pprint
import json
import re
from io import BytesIO
import warnings

# Suppress google.generativeai deprecation warning until migration to google.genai
warnings.filterwarnings('ignore', category=FutureWarning, module='google.generativeai')

import google.generativeai as genai
import questionary

import importlib.util
from pathlib import Path

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_app_config():
    config_path = Path(__file__).resolve().parent / "config.py"
    spec = importlib.util.spec_from_file_location("misinfo_app_config", config_path)
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load misinformation-agent config.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    if not hasattr(module, "APP_CONFIG"):
        raise AttributeError("APP_CONFIG missing in misinformation-agent config.")
    return module.APP_CONFIG


APP_CONFIG = _load_app_config()
from models.claim import Claim
from models.verification_result import VerificationOutput, VerificationScore
from models.media import MediaItem
from agents.claim_orchestrator_agent import ClaimOrchestratorAgent, GraphState
from logger import get_logger

logger = get_logger(__name__)

def extract_json_from_text(text: str) -> Optional[str]:
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match: return match.group(1)
    if text.strip().startswith('{'): return text
    logger.error(f"Could not find a valid JSON block in the LLM response: {text}")
    return None

class LLMClient:
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"Real LLMClient initialized with model: {self.model_name}.")

    async def extract_ticker_symbol(self, claim_text: str) -> Optional[str]:
        logger.debug(f"LLM extracting ticker for: '{claim_text}'")
        
        # Common cryptocurrency mappings
        crypto_map = {
            "bitcoin": "BTC-USD",
            "btc": "BTC-USD",
            "ethereum": "ETH-USD",
            "eth": "ETH-USD",
            "dogecoin": "DOGE-USD",
            "doge": "DOGE-USD",
            "cardano": "ADA-USD",
            "solana": "SOL-USD",
            "sol": "SOL-USD",
        }
        
        claim_lower = claim_text.lower()
        for keyword, ticker in crypto_map.items():
            if keyword in claim_lower:
                logger.info(f"Matched cryptocurrency keyword '{keyword}' to ticker '{ticker}'")
                return ticker
        
        prompt = f"""
        Identify the primary financial asset mentioned in the claim.
        Return its **Yahoo Finance Ticker Symbol**.
        Claim: "{claim_text}"
        Return ONLY the ticker symbol string (e.g., BTC-USD, AAPL, TSLA). If none, return "NULL".
        For cryptocurrencies, use format like BTC-USD, ETH-USD.
        """
        try:
            response = await self.model.generate_content_async(prompt)
            ticker = response.text.strip().replace('"', '').replace("'", "")
            if ticker.upper() == "NULL" or not ticker:
                return None
            return ticker
        except Exception as e:
            logger.warning(f"LLM ticker extraction failed: {e}")
            return None

    async def classify_claim(self, claim_text: str) -> Dict:
        logger.info(f"LLM is classifying the claim: '{claim_text}'")
        prompt = f"""
        You are an expert Claim Classifier. Classify the user's claim.

        **Available Categories:**
        - Politics
        - Health
        - Finance
        - Science
        - Education
        - General

        **User's Claim:** "{claim_text}"

        **Output Format (JSON ONLY):**
        {{
          "category": "...",
          "sub_category": "...",
          "keywords": ["...", "..."]
        }}
        """
        try:
            response = await self.model.generate_content_async(prompt)
            json_string = extract_json_from_text(response.text)
            if not json_string: raise ValueError("No JSON found in Classifier LLM response.")
            return json.loads(json_string)
        except Exception as e:
            logger.error("Error in Claim Classifier LLM, defaulting to 'General'.", exc_info=True)
            return {"category": "General", "sub_category": "General", "keywords": [claim_text]}

    async def extract_entities_ner(self, claim_text: str) -> Dict[str, List[str]]:
        """Extract named entities (PERSON, ORG, GPE) from claim using LLM."""
        logger.debug(f"Extracting entities from claim: '{claim_text}'")
        prompt = f"""
        Extract all important named entities from the claim. Focus on:
        - Person names (PERSON) - full names if available
        - Organizations (ORG)
        - Locations/Countries (GPE)
        - Important nouns and proper nouns only (NO verbs, NO common words like 'loves', 'is', 'has', 'was', 'will')
        
        Claim: "{claim_text}"
        
        Return JSON ONLY with this format:
        {{
          "persons": ["name1", "name2"],
          "organizations": ["org1", "org2"],
          "locations": ["location1", "location2"],
          "keywords": ["keyword1", "keyword2"]
        }}
        
        IMPORTANT: Do NOT include verbs or common words in keywords. Only include proper nouns and important nouns.
        """
        try:
            response = await self.model.generate_content_async(prompt)
            json_string = extract_json_from_text(response.text)
            if json_string:
                return json.loads(json_string)
        except Exception as e:
            logger.warning(f"Error extracting entities with NER: {e}")
        
        # Fallback: return empty structure
        return {"persons": [], "organizations": [], "locations": [], "keywords": []}

    async def generate_search_query(self, claim_text: str) -> Union[str, List[str]]:
        """Generate search query using NER-extracted entities. Returns a list of query variations."""
        logger.debug(f"LLM generating search query for claim: '{claim_text}'")
        
        # Extract entities using NER
        entities = await self.extract_entities_ner(claim_text)
        
        # Common stop words and verbs to filter out
        stop_words = {'loves', 'love', 'is', 'are', 'was', 'were', 'has', 'have', 'had', 'will', 'would', 
                     'should', 'could', 'may', 'might', 'can', 'must', 'do', 'does', 'did', 'the', 'a', 'an',
                     'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'about'}
        
        # Build query variations
        query_variations = []
        
        # Get all entities
        persons = entities.get("persons", [])
        organizations = entities.get("organizations", [])
        locations = entities.get("locations", [])
        keywords = [k for k in entities.get("keywords", []) if k.lower() not in stop_words]
        
        # Variation 1: Just person names (most important for news)
        if persons:
            query_variations.append(" ".join(persons[:2]))
        
        # Variation 2: Person names + organizations
        if persons and organizations:
            query_variations.append(" ".join(persons[:2] + organizations[:1]))
        
        # Variation 3: Person names + locations
        if persons and locations:
            query_variations.append(" ".join(persons[:2] + locations[:1]))
        
        # Variation 4: All entities (persons, orgs, locations, filtered keywords)
        all_entities = persons + organizations + locations + keywords
        if all_entities:
            query_variations.append(" ".join(all_entities[:5]))
        
        # Variation 5: If we have persons, try with full names or common variations
        if persons:
            # Try just the first person name (in case full name doesn't work)
            if len(persons) > 0:
                first_person_parts = persons[0].split()
                if len(first_person_parts) > 1:
                    query_variations.append(first_person_parts[0])  # Just first name
                if len(persons) > 1:
                    query_variations.append(f"{first_person_parts[0]} {persons[1]}")
        
        # Remove duplicates and empty queries, clean them
        query_variations = list(dict.fromkeys([q.strip() for q in query_variations if q.strip()]))
        
        # If we have query variations, return them
        if query_variations:
            # Clean all queries: remove newlines, extra spaces
            cleaned_variations = [" ".join(q.split()).strip() for q in query_variations]
            logger.debug(f"Generated {len(cleaned_variations)} query variations from NER entities: {cleaned_variations}")
            # Return as list if multiple, single string if one
            return cleaned_variations if len(cleaned_variations) > 1 else cleaned_variations[0]
        
        # Fallback: use LLM to generate query, but ensure it's single-line
        prompt = f"""
        Convert the claim into a concise news search query. 
        Include only proper nouns (person names, places, organizations) and important keywords.
        DO NOT include verbs like 'loves', 'is', 'has', etc.
        Return ONLY the search query text, single line, no newlines.
        Claim: "{claim_text}"
        """
        try:
            response = await self.model.generate_content_async(prompt)
            query = response.text.strip().replace('"', '').replace('\n', ' ').replace('\r', ' ')
            # Remove multiple spaces and ensure single line
            query = " ".join(query.split()).strip()
            # Filter out stop words
            query_words = [w for w in query.split() if w.lower() not in stop_words]
            query = " ".join(query_words).strip()
            return query
        except Exception:
            # Final fallback: clean the claim text itself, remove stop words
            query = re.sub(r'[?!.,]', '', claim_text).strip()
            query_words = [w for w in query.split() if w.lower() not in stop_words]
            query = " ".join(query_words).strip()
            return query

    async def summarize_long_form(self, prompt: str) -> Optional[Dict[str, Any]]:
        try:
            response = await self.model.generate_content_async(prompt)
            json_string = extract_json_from_text(response.text)
            if json_string:
                return json.loads(json_string)
        except Exception as exc:
            logger.error("Error during long-form summarization.", exc_info=exc)
        return None

    async def analyze_claim_for_mother_agent(self, claim_text: str, data: str) -> Tuple[Dict, List[str]]:
        logger.info(f"Mother LLM reasoning over claim: '{claim_text[:50]}...'")
        prompt = f"""
        You are the "Mother Agent" (Chief Investigator).
        Your goal is to connect the dots between the User's Claim and the collected Evidence.

        **User's Claim:** "{claim_text}"

        **Collected Evidence (sorted newest to oldest; pay attention to timestamps):**
        ---
        {data[:4000]} 
        ---

        **Reasoning Instructions:**
        1. Identify the core subject and specific allegations in the claim.
        2. When evidence conflicts, prioritize the most recent, credible sources (newest timestamps generally reflect the latest reality).
        3. Analyze the evidence to see if it addresses the specific subject OR the broader category.
        4. **Synthesize:** Connect facts found in the evidence to the claim with explicit references to timestamps when helpful.
        5. Provide a clear instruction for the Daughter Agent.

        **Output JSON ONLY:**
        {{
          "topic": "Detailed synthesis of how the evidence relates to the claim.",
          "recommended_daughters": ["general"]
        }}
        """
        try:
            response = await self.model.generate_content_async(prompt)
            json_string = extract_json_from_text(response.text)
            if not json_string: raise ValueError("No JSON found in Mother LLM response.")
            json_response = json.loads(json_string)
            return {"topic": json_response.get("topic", "General Analysis")}, json_response.get("recommended_daughters", ["general"])
        except Exception as e:
            logger.error("Error in Mother LLM analysis.", exc_info=True)
            return {"topic": "General Analysis"}, ["general"]

    async def analyze_image_with_prompt(
        self, prompt: str, image_bytes: bytes, mime_type: Optional[str] = None
    ) -> str:
        """
        Send an image + textual prompt to the multimodal LLM (Gemini) and return the raw text response.
        """
        try:
            from PIL import Image

            image = Image.open(BytesIO(image_bytes))
            response = await self.model.generate_content_async([prompt, image])
            return response.text
        except Exception as exc:
            logger.error("LLM image analysis failed.", exc_info=True)
            raise exc

    async def verify_for_daughter_agent(self, claim_text: str, relevant_data: List[str], prompt_instructions: Dict, domain: str) -> VerificationOutput:
        context = "\n\n".join(relevant_data)
        prompt = f"""
        You are the Daughter Agent ({domain}). Verify the claim based on the evidence provided.

        **Mother's Analysis:** "{prompt_instructions.get('topic', 'No instructions')}"

        **Claim:** "{claim_text}"

        **Evidence (newest to oldest):**
        ---
        {context[:4500]}
        ---

        **Instructions:**
        1. The Mother's analysis is a GUIDE, but you must verify based on the ACTUAL EVIDENCE provided above.
        2. If the Mother's analysis contradicts the evidence, TRUST THE EVIDENCE over the analysis.
        3. When evidence conflicts, prefer the most recent credible reporting (use timestamps provided above). Explicitly call out disagreements instead of defaulting to older information.
        4. Determine Verdict: True / False / Unverified.
        
        **Verdict Guidelines:**
        - **True**: The evidence clearly supports the claim as stated.
        - **False**: The evidence clearly contradicts the claim OR shows something different from what the claim states.
        - **Unverified**: ONLY use this if the evidence is genuinely insufficient or completely absent. Do NOT use Unverified just because there's a contradiction - contradictions usually mean False.
        
        **Important:**
        - If the claim uses ambiguous language (e.g., "loves" could mean romantic love or friendship), interpret it in the most common/natural sense.
        - If evidence shows a different type of relationship than claimed (e.g., friendship vs romantic love), the verdict should be False, not Unverified.
        - Only mark as Unverified if there is truly no relevant evidence at all.
        - Cite the timestamps or recency when explaining the verdict.
        
        **Output JSON ONLY:**
        {{
          "verdict": "True/False/Unverified",
          "explanation": "Clear explanation of why this verdict was chosen, referencing specific evidence.",
          "true_news": "If verdict is True, provide the actual fact. If False, provide what the evidence actually shows. If Unverified, state that evidence is insufficient."
        }}
        """
        placeholder_id = uuid4()
        try:
            response = await self.model.generate_content_async(prompt)
            json_string = extract_json_from_text(response.text)
            if not json_string: raise ValueError("No JSON found")
            json_response = json.loads(json_string)
            
            verdict = json_response.get("verdict", "Unverified")
            explanation = json_response.get("explanation", "")
            
            # Initial placeholder score, will be overwritten by Score Calculator
            score, confidence = 0.5, 0.0
            if verdict == "True": score = 0.9
            elif verdict == "False": score = 0.1

            return VerificationOutput(
                claim_id=placeholder_id, 
                original_claim=claim_text, 
                verdict=verdict, 
                score=VerificationScore(score=score, confidence=confidence, explanation=explanation), 
                true_news=json_response.get("true_news"), 
                sources_used=[]
            )
        except Exception as e:
            return VerificationOutput(claim_id=placeholder_id, original_claim=claim_text, verdict="Unverified", score=VerificationScore(score=0.5, confidence=0.0, explanation="Error"), sources_used=[])

async def run_pipeline(
    claim_text: str,
    use_web_search_override: Optional[bool] = None,
    external_claim_id: Optional[str] = None,
    forced_agents: Optional[List[str]] = None,
    status_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    verbose: bool = True,
    exit_on_failure: bool = True,
    media_items: Optional[List[MediaItem]] = None,
):
    try:
        logger.info("Initializing Misinformation Detector Pipeline...")

        async def notify(stage: str):
            if status_callback:
                await status_callback(stage)

        await notify("Starting pipeline")

        if use_web_search_override is None:
            use_web_search = await questionary.confirm(
                "Perform a deep web search? (Slower, uses API credits)",
                default=True
            ).ask_async()
        else:
            use_web_search = use_web_search_override

        llm_client = LLMClient(APP_CONFIG["GOOGLE_CLOUD_API_KEY"], APP_CONFIG["LLM_MODEL_NAME"])
        orchestrator = ClaimOrchestratorAgent(
            llm_client,
            APP_CONFIG,
            use_web_search,
            forced_agents or [],
            media_items or [],
            status_callback,
        )
        
        logger.info(f"--- Starting verification for raw input: '{claim_text}' ---")
        final_state: GraphState = await orchestrator.run_workflow(
            claim_text, external_claim_id=external_claim_id
        )
        
        final_output = final_state.get('final_verification_output')

        if verbose:
            print("\n" + "="*60 + "\n--- VERIFICATION COMPLETE ---\n" + "="*60)
            if final_output:
                print(f"  Claim:    {final_output.original_claim}")
                print(f"  Verdict:  {final_output.verdict}")
                # Updated to show score as a percentage or confidence
                print(f"  Score:    {final_output.score.score:.2f} (Confidence: {final_output.score.confidence:.2f})")
                print(f"  Summary:  {final_output.score.explanation}")
                if final_output.true_news:
                    print(f"  Fact:     {final_output.true_news}")
                
                if final_state.get('agents_used'):
                    print("\n  Data Collection Agents Used:")
                    for agent_name in final_state['agents_used']:
                        print(f"    - {agent_name.split('.')[-1]}")
        
                if final_output.sources_used:
                    print("\n  Sources Found:")
                    for source in final_output.sources_used:
                        print(f"    - [{source.source_name}]({source.url})")
            else:
                print("  ERROR: Could not produce a final verification output.")
            print("="*60)

        await notify("Completed")
        return final_state

    except Exception as e:
        if status_callback:
            await status_callback("Failed")
        logger.critical("An unhandled exception occurred in the pipeline.", exc_info=True)
        if verbose:
            print(f"\nFATAL ERROR: A critical error occurred. Check the 'app.log' file for details.")
        if exit_on_failure:
            sys.exit(1)
        raise
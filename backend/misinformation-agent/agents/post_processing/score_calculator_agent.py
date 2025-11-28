from typing import List, Any
from urllib.parse import urlparse
import importlib.util
from pathlib import Path

import numpy as np
from huggingface_hub import InferenceClient

from models.claim import Claim
from models.collected_data import CollectedDataBundle
from models.verification_result import VerificationOutput
import sys

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from logger import get_logger


def _load_app_config():
    config_path = Path(__file__).resolve().parents[2] / "config.py"
    spec = importlib.util.spec_from_file_location("misinfo_app_config_score", config_path)
    if spec is None or spec.loader is None:
        raise ImportError("Unable to load misinformation-agent APP_CONFIG.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    if not hasattr(module, "APP_CONFIG"):
        raise AttributeError("APP_CONFIG missing in misinformation-agent config.")
    return module.APP_CONFIG


APP_CONFIG = _load_app_config()

logger = get_logger(__name__)
SEPARATOR = "-" * 100

# --- DOMAIN AUTHORITY DATABASE ---
DOMAIN_SCORES = {
    # Tier 1: Official / Gov
    "gov": 1.0, "mil": 1.0, "edu": 1.0, "int": 1.0,
    "who.int": 1.0, "cdc.gov": 1.0, "nih.gov": 1.0, "un.org": 1.0,
    "pib.gov.in": 1.0, "whitehouse.gov": 1.0, "nasa.gov": 1.0,
    "rbi.org.in": 1.0, "sec.gov": 1.0,
    
    # Tier 2: Fact Checkers & Wire Services
    "reuters.com": 0.95, "apnews.com": 0.95, "afp.com": 0.95, "ptinews.com": 0.95,
    "bloomberg.com": 0.9, "snopes.com": 0.9, "politifact.com": 0.9,
    "altnews.in": 0.9, "boomlive.in": 0.9, "factcheck.org": 0.9,
    
    # Tier 3: High Quality News
    "bbc.com": 0.85, "nytimes.com": 0.85, "washingtonpost.com": 0.85,
    "thehindu.com": 0.85, "indianexpress.com": 0.85, "ndtv.com": 0.8,
    "timesofindia.indiatimes.com": 0.8, "wsj.com": 0.85, "ft.com": 0.85,
    "economictimes.indiatimes.com": 0.8, "cnbc.com": 0.8, "livemint.com": 0.8,
    
    # Tier 4: Encyclopedias
    "wikipedia.org": 0.75,
}

def get_domain_authority(url: str) -> float:
    try:
        domain = urlparse(url).netloc.replace("www.", "").lower()
        if domain in DOMAIN_SCORES: return DOMAIN_SCORES[domain]
        
        if domain.endswith(".gov") or domain.endswith(".gov.in") or domain.endswith(".nic.in"): return 1.0
        if domain.endswith(".edu") or domain.endswith(".ac.in"): return 0.9
        
        for key, score in DOMAIN_SCORES.items():
            if key in domain: return score
            
        return 0.5 
    except:
        return 0.4

# --- LIGHTWEIGHT SIMILARITY LOGIC ---

def get_hf_embeddings(texts: List[str], api_key: str) -> np.ndarray:
    """
    Fetches embeddings from Hugging Face Inference API.
    Model: sentence-transformers/all-MiniLM-L6-v2
    """
    if not api_key:
        logger.error("HUGGINGFACE_API_KEY is missing. Returning zero vectors.")
        return np.zeros((len(texts), 384))

    client = InferenceClient(token=api_key)
    model_id = "sentence-transformers/all-MiniLM-L6-v2"

    try:
        # feature_extraction returns a list of lists (vectors)
        embeddings = client.feature_extraction(texts, model=model_id)
        # Convert to numpy array
        return np.array(embeddings)
    except Exception as e:
        logger.error(f"Hugging Face API failed: {e}")
        return np.zeros((len(texts), 384)) # 384 is dim of MiniLM

def manual_cosine_similarity(vec_a, vec_b):
    """
    Calculate cosine similarity between two vectors without sklearn.
    """
    dot_product = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

async def run(
    claim: Claim, 
    collected_data: CollectedDataBundle, 
    verification_result: VerificationOutput,
    agents_used: List[str]
) -> VerificationOutput:
    
    logger.info(SEPARATOR)
    logger.info("--- SCORE CALCULATOR AGENT (HF INFERENCE) BEING CALLED ---")
    
    if verification_result.verdict == "Unverified":
        logger.info("Verdict is Unverified. Setting confidence to 0.0")
        verification_result.score.confidence = 0.0
        logger.info("--- SCORE CALCULATOR FINISHED ---")
        logger.info(SEPARATOR)
        return verification_result

    sources = collected_data.data
    if not sources:
        logger.warning("No sources found in bundle. Confidence is 0.")
        verification_result.score.confidence = 0.0
        logger.info("--- SCORE CALCULATOR FINISHED ---")
        logger.info(SEPARATOR)
        return verification_result

    # 1. Authority Score
    total_auth_score = 0.0
    unique_domains = set()
    evidence_texts = []
    
    for item in sources:
        auth = get_domain_authority(item.meta.url)
        total_auth_score += auth
        unique_domains.add(urlparse(item.meta.url).netloc)
        # Collect text (Claim + first 400 chars of content) for similarity
        evidence_texts.append(item.content[:400])
        
    avg_authority_score = total_auth_score / len(sources)
    logger.info(f"Average Domain Authority Score: {avg_authority_score:.2f}")

    # 2. Corroboration Score
    source_count = len(unique_domains)
    if source_count == 1: corroboration_score = 0.5
    elif source_count <= 3: corroboration_score = 0.8
    else: corroboration_score = 1.0
    logger.info(f"Corroboration Score ({source_count} unique sources): {corroboration_score:.2f}")

    # 3. Semantic Similarity Score (via Hugging Face)
    similarity_score = 0.5 # Default
    hf_key = APP_CONFIG.get("HUGGINGFACE_API_KEY")
    
    if hf_key and evidence_texts:
        # Get embedding for claim
        claim_emb = get_hf_embeddings([claim.text], hf_key)[0]
        
        # Get embeddings for top 5 evidence pieces
        evidence_embs = get_hf_embeddings(evidence_texts[:5], hf_key)
        
        # Find max similarity
        max_sim = 0.0
        for ev_emb in evidence_embs:
            sim = manual_cosine_similarity(claim_emb, ev_emb)
            if sim > max_sim:
                max_sim = sim
        
        similarity_score = float(max_sim)
        logger.info(f"Semantic Similarity Score (HF Inference): {similarity_score:.2f}")
    else:
        logger.warning("Skipping similarity check (No HF Key or no evidence text).")

    # 4. Fact Check Bonus
    fact_check_bonus = 0.0
    if "agents.data_collection.google_fact_check_agent" in agents_used:
        # We check if the agent actually contributed data
        if any(s.meta.agent_name == "Google_FactCheck_Agent" for s in sources):
            logger.info("Fact Check Agent found results. Applying Bonus.")
            fact_check_bonus = 0.15

    # --- FINAL CALCULATION ---
    raw_confidence = (avg_authority_score * 0.4) + (similarity_score * 0.3) + (corroboration_score * 0.3) + fact_check_bonus
    final_confidence = min(0.99, max(0.0, raw_confidence))
    
    logger.info(f"Calculated Math Confidence: {final_confidence:.2f}")

    verification_result.score.confidence = round(final_confidence, 2)
    verification_result.score.score = round(final_confidence * 100, 1)

    logger.info("--- SCORE CALCULATOR FINISHED ---")
    logger.info(SEPARATOR)
    return verification_result
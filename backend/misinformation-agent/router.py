from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from auth.router import get_current_user
from database import db, get_next_sequence
from data_manager import initialize_data_directory
from agentic_pipeline import run_pipeline
from schema import (
    ClaimAnalyzeRequest,
    ClaimAnalyzeResponse,
    ClaimAgentRecord,
    ClaimVerdictDBSchema,
    SourceSchema,
)
from models.media import MediaItem
from config import ASSEMBLY_AI_API_KEY
from logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
ASSEMBLY_BASE_URL = "https://api.assemblyai.com"

AGENT_FILE_METADATA: Dict[str, Dict[str, str]] = {
    "mother_agent_analysis": {"agent_name": "Mother Agent", "agent_type": "analysis"},
    "gnews_data": {"agent_name": "GNews API Agent", "agent_type": "news"},
    "fact_check_data": {"agent_name": "Google Fact Check Agent", "agent_type": "fact_check"},
    "political_data": {"agent_name": "Political Agent", "agent_type": "domain"},
    "finance_data": {"agent_name": "Finance Agent", "agent_type": "domain"},
    "health_data": {"agent_name": "Health Agent", "agent_type": "domain"},
    "wikipedia_data": {"agent_name": "Wikipedia Agent", "agent_type": "reference"},
    "web_search_data": {"agent_name": "Web Search Agent", "agent_type": "search"},
    "scraped_content_data": {"agent_name": "URL Scraper Agent", "agent_type": "scraper"},
    "image_claim_data": {"agent_name": "Image Claim Agent", "agent_type": "media"},
    "sentiment_analysis": {"agent_name": "Sentiment Analysis Agent", "agent_type": "post_processing"},
    "emotion_analysis": {"agent_name": "Emotion Analysis Agent", "agent_type": "post_processing"},
}

router = APIRouter(prefix="/claims", tags=["Claims"])


def _load_json(filename: str) -> Optional[Any]:
    file_path = DATA_DIR / filename
    if not file_path.exists():
        return None
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_timestamp(raw_ts: str) -> Optional[datetime]:
    if not raw_ts:
        return None
    try:
        return datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_sources(raw_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for source in raw_sources:
        sources.append(
            SourceSchema(
                url=source.get("url", ""),
                source_name=source.get("source_name", "Unknown"),
                agent_name=source.get("agent_name"),
                timestamp=_parse_timestamp(source.get("timestamp", "")),
            ).model_dump()
        )
    return sources


async def _upload_audio_to_assembly(audio_bytes: bytes) -> str:
    if not ASSEMBLY_AI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="AssemblyAI API key not configured on the server.",
        )
    headers = {"authorization": ASSEMBLY_AI_API_KEY}
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{ASSEMBLY_BASE_URL}/v2/upload",
            headers=headers,
            content=audio_bytes,
        )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"AssemblyAI upload failed: {response.text}",
            )
        data = response.json()
        upload_url = data.get("upload_url")
        if not upload_url:
            raise HTTPException(status_code=502, detail="Invalid upload response from AssemblyAI.")
        return upload_url


async def _create_transcript(audio_url: str) -> str:
    headers = {
        "authorization": ASSEMBLY_AI_API_KEY,
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{ASSEMBLY_BASE_URL}/v2/transcript",
            headers=headers,
            json={"audio_url": audio_url},
        )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"AssemblyAI transcription request failed: {response.text}",
            )
        data = response.json()
        transcript_id = data.get("id")
        if not transcript_id:
            raise HTTPException(status_code=502, detail="Invalid transcript response from AssemblyAI.")
        return transcript_id


async def _poll_transcript(transcript_id: str, *, timeout_seconds: int = 120, poll_interval: float = 2.0) -> str:
    headers = {"authorization": ASSEMBLY_AI_API_KEY}
    start = asyncio.get_event_loop().time()
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            response = await client.get(
                f"{ASSEMBLY_BASE_URL}/v2/transcript/{transcript_id}",
                headers=headers,
            )
            if response.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=f"AssemblyAI polling failed: {response.text}",
                )
            payload = response.json()
            status_value = payload.get("status")
            if status_value == "completed":
                return payload.get("text", "")
            if status_value == "error":
                raise HTTPException(
                    status_code=502,
                    detail=f"Transcription failed: {payload.get('error')}",
                )
            if asyncio.get_event_loop().time() - start > timeout_seconds:
                raise HTTPException(status_code=504, detail="AssemblyAI transcription timed out.")
            await asyncio.sleep(poll_interval)


async def _transcribe_audio_bytes(audio_bytes: bytes) -> str:
    upload_url = await _upload_audio_to_assembly(audio_bytes)
    transcript_id = await _create_transcript(upload_url)
    return await _poll_transcript(transcript_id)


async def _persist_pipeline_outputs(
    *,
    claim_id: str,
    user_id: Union[str, int],
    claim_text: str,
    use_web_search: bool,
    forced_agents: List[str],
) -> None:
    final_verdict = _load_json("final_verdict.json")
    if not final_verdict:
        raise ValueError("Final verdict data not found.")

    classification = _load_json("claim_classification.json") or {}
    score_block = final_verdict.get("score", {})
    
    # Load sentiment and emotion analysis results
    sentiment_data = _load_json("sentiment_analysis.json")
    emotion_data = _load_json("emotion_analysis.json")

    display_claim_text = final_verdict.get("original_claim", claim_text)

    verdict_payload = ClaimVerdictDBSchema(
        claimId=claim_id,
        userId=user_id,
        claim_text=display_claim_text,
        status="completed",
        processing_stage="Completed",
        verdict=final_verdict.get("verdict"),
        confidence=score_block.get("confidence"),
        score={
            "score": score_block.get("score", 0.0),
            "confidence": score_block.get("confidence", 0.0),
            "explanation": score_block.get("explanation", ""),
        }
        if score_block
        else None,
        true_news=final_verdict.get("true_news"),
        summary=score_block.get("explanation"),
        category=classification.get("category"),
        sub_category=classification.get("sub_category"),
        keywords=classification.get("keywords", []),
        sources_used=_build_sources(final_verdict.get("sources_used", [])),
        sentiment_analysis=sentiment_data,
        emotion_analysis=emotion_data,
        metadata={"use_web_search": use_web_search, "forced_agents": forced_agents},
        updated_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    ).model_dump()

    # Preserve original created_at if it exists
    existing = await db.claim_verdicts.find_one({"claimId": claim_id}, {"created_at": 1})
    if existing and existing.get("created_at"):
        verdict_payload["created_at"] = existing["created_at"]

    await db.claim_verdicts.update_one(
        {"claimId": claim_id},
        {"$set": verdict_payload},
        upsert=True,
    )

    # Persist agent outputs
    await db.claim_agents.delete_many({"claimId": claim_id})
    agent_documents: List[Dict[str, Any]] = []

    for json_file in DATA_DIR.glob("*.json"):
        stem = json_file.stem
        if stem in {"final_verdict", "claim_classification"}:
            continue

        data = _load_json(json_file.name)
        if data is None:
            continue

        meta = AGENT_FILE_METADATA.get(
            stem,
            {
                "agent_name": stem.replace("_", " ").title(),
                "agent_type": "general",
            },
        )

        agent_doc = ClaimAgentRecord(
            claimId=claim_id,
            agent_key=stem,
            agent_name=meta["agent_name"],
            agent_type=meta["agent_type"],
            output=data,
        ).model_dump()

        # Attach relevance score if obvious
        agent_documents.append(agent_doc)

    if agent_documents:
        await db.claim_agents.insert_many(agent_documents)


async def _process_claim(
    *,
    claim_id: str,
    user_id: Union[str, int],
    claim_text: str,
    use_web_search: bool,
    forced_agents: List[str],
    media: List[MediaItem],
) -> None:
    async def update_stage(stage: str):
        await db.claim_verdicts.update_one(
            {"claimId": claim_id},
            {
                "$set": {
                    "processing_stage": stage,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    try:
        await update_stage("Initializing pipeline")
        initialize_data_directory()
        await run_pipeline(
            claim_text,
            use_web_search_override=use_web_search,
            forced_agents=forced_agents,
            status_callback=update_stage,
            verbose=False,
            exit_on_failure=False,
            media_items=media,
        )
        await _persist_pipeline_outputs(
            claim_id=claim_id,
            user_id=user_id,
            claim_text=claim_text,
            use_web_search=use_web_search,
            forced_agents=forced_agents,
        )
    except Exception as exc:
        logger.error(f"Claim processing failed for claim_id {claim_id}: {exc}", exc_info=True)
        await db.claim_verdicts.update_one(
            {"claimId": claim_id},
            {
                "$set": {
                    "status": "failed",
                    "processing_stage": "Failed",
                    "error": {"message": str(exc)},
                    "updated_at": datetime.utcnow(),
                }
            },
        )


@router.post("/analyze", response_model=ClaimAnalyzeResponse, status_code=status.HTTP_202_ACCEPTED)
async def analyze_claim(
    request: ClaimAnalyzeRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id") or str(current_user["_id"])
    logger.info(f"Claim analysis requested by user {user_id}: text_length={len(request.claim_text)}, media_count={len(request.media)}")
    
    if not request.claim_text.strip() and not request.media:
        logger.warning(f"Claim analysis rejected: No text or media provided by user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a textual claim or at least one media attachment.",
        )
    forced_agents = sorted(
        {
            agent
            for agent in request.forced_agents
            if agent in {"wikipedia", "political", "health", "finance"}
        }
    )
    claim_seq = await get_next_sequence("claims")
    claim_id = str(claim_seq)
    now = datetime.utcnow()
    
    logger.info(f"Created claim {claim_id} for user {user_id}, forced_agents={forced_agents}")

    initial_doc = ClaimVerdictDBSchema(
        claimId=claim_id,
        userId=user_id,
        claim_text=request.claim_text,
        status="processing",
        processing_stage="Queued",
        metadata={
            "use_web_search": request.use_web_search,
            "forced_agents": forced_agents,
            "media_count": len(request.media),
        },
        created_at=now,
        updated_at=now,
    ).model_dump()
    await db.claim_verdicts.insert_one(initial_doc)

    asyncio.create_task(
        _process_claim(
            claim_id=claim_id,
            user_id=user_id,
            claim_text=request.claim_text,
            use_web_search=request.use_web_search,
            forced_agents=forced_agents,
            media=request.media,
        )
    )

    return ClaimAnalyzeResponse(claimId=claim_id, status="processing")


@router.get("/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """Get dashboard statistics for the current user."""
    # user_id is stored as int in users collection
    user_id = current_user.get("user_id")
    if user_id is None:
        logger.warning(f"No user_id in current_user, keys: {list(current_user.keys())}")
        return {
            "total_claims": 0,
            "fake_detected": 0,
            "real_verified": 0,
            "mixed_unverified": 0,
            "average_confidence": 0,
            "average_analysis_time": 0,
        }
    
    # userId in claim_verdicts might be None or missing in some old claims
    # Query for claims where userId matches OR userId is None/missing (for backward compatibility)
    query = {
        "$or": [
            {"userId": user_id},
            {"userId": {"$in": [int(user_id), str(user_id)]}},
            {"userId": None},
            {"userId": {"$exists": False}},
        ]
    }
    
    logger.info(f"Dashboard stats query: user_id={user_id} (type: {type(user_id).__name__}), query={query}")
    
    # Get all claims for this user (including those with missing userId for backward compatibility)
    all_claims = await db.claim_verdicts.find(
        query,
        {
            "userId": 1,
            "verdict": 1,
            "confidence": 1,
            "created_at": 1,
            "completed_at": 1,
            "status": 1,
            "claimId": 1,
        }
    ).to_list(length=None)
    
    # Filter to include claims that match user_id OR have None/missing userId (for backward compatibility)
    # If all claims have None userId, assume they belong to the current user
    matching_claims = [c for c in all_claims if c.get("userId") == user_id or c.get("userId") == int(user_id) or c.get("userId") == str(user_id)]
    none_claims = [c for c in all_claims if c.get("userId") is None or c.get("userId") == "None" or "userId" not in c]
    
    # Use matching claims if available, otherwise use None claims (backward compatibility)
    claims = matching_claims if matching_claims else none_claims
    
    logger.info(f"Found {len(all_claims)} total claims: {len(matching_claims)} matching user_id={user_id}, {len(none_claims)} with None userId")
    
    # Debug: log a sample claim to see userId format
    if all_claims:
        sample = all_claims[0]
        logger.info(f"Sample claim userId type: {type(sample.get('userId')).__name__}, value: {sample.get('userId')}")
    
    if not claims:
        return {
            "total_claims": 0,
            "fake_detected": 0,
            "real_verified": 0,
            "mixed_unverified": 0,
            "average_confidence": 0,
            "average_analysis_time": 0,
        }
    
    total_claims = len(claims)
    
    # Debug: log verdict and status values
    verdict_counts = {}
    status_counts = {}
    for c in claims:
        verdict = c.get("verdict")
        status = c.get("status")
        verdict_str = str(verdict) if verdict is not None else "None"
        status_str = str(status) if status is not None else "None"
        verdict_counts[verdict_str] = verdict_counts.get(verdict_str, 0) + 1
        status_counts[status_str] = status_counts.get(status_str, 0) + 1
    logger.info(f"Verdict breakdown: {verdict_counts}")
    logger.info(f"Status breakdown: {status_counts}")
    
    # Count verdicts - check for both string and boolean values (handle case variations)
    fake_detected = sum(1 for c in claims if str(c.get("verdict", "")).lower() in ("false", "unverified") or c.get("verdict") is False)
    real_verified = sum(1 for c in claims if str(c.get("verdict", "")).lower() == "true" or c.get("verdict") is True)
    mixed_unverified = sum(1 for c in claims if c.get("verdict") in ("mixed", "unknown") or (c.get("verdict") is None and c.get("status") == "completed"))
    
    logger.info(f"Calculated stats: total={total_claims}, fake={fake_detected}, real={real_verified}, mixed={mixed_unverified}")
    
    # Calculate average confidence
    confidences = [c.get("confidence", 0) for c in claims if c.get("confidence") is not None]
    average_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    # Calculate average analysis time
    analysis_times = []
    for claim in claims:
        if claim.get("created_at") and claim.get("completed_at"):
            try:
                created = claim["created_at"]
                completed = claim["completed_at"]
                if isinstance(created, str):
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if isinstance(completed, str):
                    completed = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                if isinstance(created, datetime) and isinstance(completed, datetime):
                    delta = (completed - created).total_seconds()
                    if delta > 0:
                        analysis_times.append(delta)
            except Exception:
                pass
    
    average_analysis_time = sum(analysis_times) / len(analysis_times) if analysis_times else 0
    
    return {
        "total_claims": total_claims,
        "fake_detected": fake_detected,
        "real_verified": real_verified,
        "mixed_unverified": mixed_unverified,
        "average_confidence": round(average_confidence * 100, 1),  # Convert to percentage
        "average_analysis_time": round(average_analysis_time, 1),  # In seconds
    }


@router.get("/top-misinformation")
async def get_top_misinformation(
    limit: int = 5,
    current_user: dict = Depends(get_current_user),
):
    """Get top misinformation claims (verdict: false) for the current user."""
    user_id = current_user.get("user_id")
    if user_id is None:
        logger.warning(f"No user_id found in current_user: {current_user.keys()}")
        return {"claims": []}
    
    # userId in claim_verdicts might be None or missing in some old claims
    # Query for claims where userId matches AND verdict is false (handle both string and boolean)
    query = {
        "$and": [
            {
                "$or": [
                    {"userId": user_id},
                    {"userId": {"$in": [int(user_id), str(user_id)]}},
                ]
            },
            {
                "$or": [
                    {"verdict": "false"},
                    {"verdict": "False"},
                    {"verdict": False},
                    {"verdict": "Unverified"},  # Some claims might be marked as "Unverified" instead of "false"
                ]
            },
            {
                "$or": [
                    {"status": "completed"},
                    {"status": {"$exists": False}},  # Include claims without status field
                ]
            },
        ]
    }
    
    logger.info(f"Top misinformation query: user_id={user_id}, query={query}")
    
    claims = await db.claim_verdicts.find(
        query,
        {
            "claimId": 1,
            "claim_text": 1,
            "verdict": 1,
            "confidence": 1,
            "created_at": 1,
            "summary": 1,
            "status": 1,
        }
    ).sort("created_at", -1).limit(min(limit, 10)).to_list(length=None)
    
    logger.info(f"Found {len(claims)} misinformation claims for user_id={user_id}")
    
    # Debug: log sample verdict values
    if claims:
        sample = claims[0]
        logger.info(f"Sample misinformation claim: verdict={sample.get('verdict')} (type: {type(sample.get('verdict')).__name__}), status={sample.get('status')}")
    
    result = []
    for claim in claims:
        result.append({
            "claimId": claim.get("claimId"),
            "claim_text": claim.get("claim_text", "")[:100] + "..." if len(claim.get("claim_text", "")) > 100 else claim.get("claim_text", ""),
            "confidence": round((claim.get("confidence", 0) * 100), 1) if claim.get("confidence") else 0,
            "created_at": claim.get("created_at").isoformat() if claim.get("created_at") else None,
            "summary": claim.get("summary", "")[:150] + "..." if len(claim.get("summary", "")) > 150 else claim.get("summary", ""),
        })
    
    return {"claims": result}


@router.get("/trending-topics")
async def get_trending_topics(
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
):
    """Get trending topics/keywords from user's claims."""
    import re
    from collections import Counter
    
    user_id = current_user.get("user_id")
    if user_id is None:
        logger.warning(f"No user_id found in current_user: {current_user.keys()}")
        return {"topics": []}
    
    # Query for completed claims
    query = {
        "$or": [
            {"userId": user_id},
            {"userId": {"$in": [int(user_id), str(user_id)]}},
        ]
    }
    
    claims = await db.claim_verdicts.find(
        query,
        {"claim_text": 1}
    ).to_list(length=None)
    
    if not claims:
        return {"topics": []}
    
    # Extract keywords from claim_text
    # Common stop words to filter out
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "as", "is", "was", "are", "were", "been", "be", "have", "has", "had",
        "do", "does", "did", "will", "would", "should", "could", "may", "might", "must",
        "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they",
        "what", "which", "who", "when", "where", "why", "how", "can", "about", "into",
        "through", "during", "including", "against", "among", "throughout", "despite",
        "towards", "upon", "concerning", "to", "of", "in", "for", "on", "at", "by",
        "with", "about", "into", "through", "during", "including", "against", "among",
        "throughout", "despite", "towards", "upon", "concerning", "is", "are", "was",
        "were", "been", "be", "have", "has", "had", "do", "does", "did", "will", "would",
        "should", "could", "may", "might", "must", "can", "cannot", "couldn", "wouldn",
        "shouldn", "won", "mustn", "needn", "daren", "oughtn", "mightn", "shan"
    }
    
    # Extract words from claim texts
    all_words = []
    for claim in claims:
        text = claim.get("claim_text", "").lower()
        # Remove URLs, special characters, keep only alphanumeric and spaces
        text = re.sub(r'http\S+|www\.\S+', '', text)
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        # Filter: length >= 3, not a stop word, not a number
        words = [w for w in words if len(w) >= 3 and w not in stop_words and not w.isdigit()]
        all_words.extend(words)
    
    # Count word frequency
    word_counts = Counter(all_words)
    
    # Get top N topics
    top_topics = word_counts.most_common(limit)
    
    result = []
    for word, count in top_topics:
        result.append({
            "topic": word.capitalize(),
            "count": count,
            "frequency": count
        })
    
    logger.info(f"Found {len(result)} trending topics for user_id={user_id}")
    return {"topics": result}


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id") or str(current_user["_id"])
    logger.info(f"Audio transcription requested by user {user_id}, filename={file.filename}")
    audio_bytes = await file.read()
    if not audio_bytes:
        logger.warning(f"Audio transcription failed: Empty file from user {user_id}")
        raise HTTPException(status_code=400, detail="Audio file is empty.")
    if len(audio_bytes) > 25 * 1024 * 1024:
        logger.warning(f"Audio transcription failed: File too large ({len(audio_bytes)} bytes) from user {user_id}")
        raise HTTPException(status_code=400, detail="Audio file exceeds 25 MB limit.")
    logger.info(f"Transcribing audio for user {user_id}, size={len(audio_bytes)} bytes")
    transcript_text = await _transcribe_audio_bytes(audio_bytes)
    logger.info(f"Audio transcription completed for user {user_id}, transcript_length={len(transcript_text)}")
    return {"text": transcript_text}


@router.get("")
async def list_claims(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("user_id") or str(current_user["_id"])
    cursor = (
        db.claim_verdicts.find({"userId": user_id})
        .sort("created_at", -1)
        .limit(max(1, min(limit, 100)))
    )
    claims: List[Dict[str, Any]] = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        claims.append(doc)
    return {"claims": claims}


@router.get("/{claim_id}")
async def get_claim(claim_id: str, current_user: dict = Depends(get_current_user)):
    doc = await db.claim_verdicts.find_one(
        {
            "claimId": claim_id,
            "userId": current_user.get("user_id") or str(current_user["_id"]),
        }
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Claim not found")
    doc["_id"] = str(doc["_id"])
    return doc


@router.get("/{claim_id}/agents")
async def get_claim_agents(claim_id: str, current_user: dict = Depends(get_current_user)):
    # Ensure the claim belongs to the user
    exists = await db.claim_verdicts.find_one(
        {
            "claimId": claim_id,
            "userId": current_user.get("user_id") or str(current_user["_id"]),
        },
        {"_id": 1},
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Claim not found")

    cursor = db.claim_agents.find({"claimId": claim_id})
    agents = []
    async for record in cursor:
        record["_id"] = str(record["_id"])
        agents.append(record)
    return {"claimId": claim_id, "agents": agents}


@router.delete("/{claim_id}")
async def delete_claim(claim_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("user_id") or str(current_user["_id"])
    result = await db.claim_verdicts.delete_one({"claimId": claim_id, "userId": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Claim not found")
    await db.claim_agents.delete_many({"claimId": claim_id})
    return {"deleted": True}


from __future__ import annotations

import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from models.claim import Claim
from models.media import MediaItem
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

PROMPT_TEMPLATE = """
You are the Image Claim Extraction Agent.
Analyze the provided news-style image and extract every factual statement present.

Context (user text, may be blank):
"{user_context}"

**Tasks**
1. Transcribe ALL textual content verbatim (headline, sub-head, ticker, captions).
2. Identify publisher logos/branding (e.g., News18, BBC).
3. Summarize the visual scene (who/what is depicted).
4. List explicit factual claims or directives in the graphic.
5. Flag suspicious design cues (mismatched fonts, inconsistent logos, watermarks).

**Output JSON ONLY**
{{
  "headline": "primary headline text or empty string",
  "subtext": ["additional lines"],
  "publisher": "publisher name if visible",
  "detected_claims": [
    {{"text": "...", "confidence": 0.0-1.0}}
  ],
  "visual_description": "describe people/objects/scenario",
  "logos": ["list of detected logos or text on badges"],
  "timestamp_strings": ["date/time strings if seen"],
  "suspicious_elements": ["list of red flags or leave empty"],
  "overall_confidence": 0.0-1.0
}}
Strictly return valid JSON. Do not add commentary outside JSON.
"""


def _extract_json_from_text(text: str) -> Optional[str]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    return None


def _strip_base64_header(data: str) -> str:
    return data.split(",", 1)[-1] if "," in data else data


async def _load_image_bytes(media: MediaItem) -> Tuple[bytes, str]:
    if media.data_base64:
        try:
            return base64.b64decode(_strip_base64_header(media.data_base64)), media.mime_type or "image/png"
        except Exception as exc:
            raise ValueError(f"Invalid base64 payload for media {media.filename or 'image'}: {exc}") from exc

    if media.url:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(str(media.url), follow_redirects=True)
            response.raise_for_status()
            mime = response.headers.get("content-type", media.mime_type or "application/octet-stream")
            return response.content, mime

    raise ValueError("Media item missing both url and data payload.")


def _build_source_meta(media: MediaItem, agent_suffix: str) -> SourceMetaData:
    source_url = str(media.url) if media.url else f"uploaded://{media.filename or 'image'}"
    return SourceMetaData(
        url=source_url,
        source_name=media.description or "User-supplied media",
        agent_name=f"image_claim_agent.{agent_suffix}",
    )


async def _analyze_single_image(
    media: MediaItem,
    claim: Claim,
    llm_client: Any,
) -> Dict[str, Any]:
    image_bytes, mime_type = await _load_image_bytes(media)
    prompt = PROMPT_TEMPLATE.format(user_context=claim.text or "")

    raw_response = await llm_client.analyze_image_with_prompt(prompt, image_bytes, mime_type)
    json_payload = _extract_json_from_text(raw_response)

    if not json_payload:
        logger.warning("LLM did not return JSON for media %s", media.filename or media.url)
        raise ValueError("LLM response missing JSON block.")

    parsed = json.loads(json_payload)
    parsed["raw_response"] = raw_response
    return parsed


async def run(
    *,
    claim: Claim,
    media_items: List[MediaItem],
    llm_client: Any,
) -> Dict[str, Any]:
    """
    Process one or more image attachments, extract textual claims, and return structured evidence.
    """
    image_items = [media for media in media_items if media.type == "image"]
    if not image_items:
        return {"extracted_claims": [], "collected_items": [], "errors": ["No image media provided."]}

    logger.info(SEPARATOR)
    logger.info("--- IMAGE CLAIM AGENT START ---")
    logger.info("Processing %d image attachment(s).", len(image_items))

    collected_items: List[CollectedDataItem] = []
    extracted_claims: List[Dict[str, Any]] = []
    errors: List[str] = []
    raw_outputs: List[Dict[str, Any]] = []

    for idx, media in enumerate(image_items, start=1):
        try:
            parsed = await _analyze_single_image(media, claim, llm_client)
            raw_outputs.append(parsed)

            headline = parsed.get("headline", "").strip()
            subtext = parsed.get("subtext", [])
            publisher = parsed.get("publisher")
            visual_description = parsed.get("visual_description")
            logos = parsed.get("logos", [])
            suspicious = parsed.get("suspicious_elements", [])
            timestamp_strings = parsed.get("timestamp_strings", [])
            detected_claims = parsed.get("detected_claims", [])

            if detected_claims:
                for claim_obj in detected_claims:
                    if not claim_obj.get("text"):
                        continue
                    extracted_claims.append(
                        {
                            "text": claim_obj["text"],
                            "confidence": claim_obj.get("confidence", 0.0),
                            "source_image": media.filename or media.url or f"image_{idx}",
                        }
                    )

            summary_lines = []
            if headline:
                summary_lines.append(f"Headline: {headline}")
            if subtext:
                summary_lines.append("Subtext:\n- " + "\n- ".join(subtext))
            if publisher:
                summary_lines.append(f"Publisher: {publisher}")
            if timestamp_strings:
                summary_lines.append("Timestamps:\n- " + "\n- ".join(timestamp_strings))

            if summary_lines:
                collected_items.append(
                    CollectedDataItem(
                        content="\n".join(summary_lines),
                        relevance_score=0.95,
                        meta=_build_source_meta(media, "ocr"),
                    )
                )

            if visual_description:
                collected_items.append(
                    CollectedDataItem(
                        content=f"Visual Description: {visual_description}",
                        relevance_score=0.7,
                        meta=_build_source_meta(media, "visual"),
                    )
                )

            if logos:
                collected_items.append(
                    CollectedDataItem(
                        content="Detected logos/branding: " + ", ".join(logos),
                        relevance_score=0.8,
                        meta=_build_source_meta(media, "branding"),
                    )
                )

            if suspicious:
                collected_items.append(
                    CollectedDataItem(
                        content="Suspicious Elements:\n- " + "\n- ".join(suspicious),
                        relevance_score=0.6,
                        meta=_build_source_meta(media, "suspicion"),
                    )
                )

        except Exception as exc:
            logger.error("Image claim agent failed for media %s", media.filename or media.url, exc_info=True)
            errors.append(str(exc))

    primary_claim = None
    if extracted_claims:
        primary_claim = max(extracted_claims, key=lambda item: item.get("confidence", 0.0)).get("text")

    logger.info("--- IMAGE CLAIM AGENT FINISH ---")
    logger.info(SEPARATOR)

    return {
        "primary_claim": primary_claim,
        "extracted_claims": extracted_claims,
        "collected_items": collected_items,
        "errors": errors,
        "raw_outputs": raw_outputs,
    }


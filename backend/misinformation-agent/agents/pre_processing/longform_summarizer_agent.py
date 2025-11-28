from __future__ import annotations

from typing import Any, Dict, Optional
import sys
from pathlib import Path

# Ensure backend root is importable for shared modules (logger, models, etc.)
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from logger import get_logger
from models.collected_data import CollectedDataItem, SourceMetaData

logger = get_logger(__name__)
SEPARATOR = "-" * 100

SUMMARY_PROMPT = """
You are a fact-check assistant. Given the article or claim text below, create a structured summary.

Return STRICT JSON with:
{{
  "source": "<short label>",
  "headline": "<best title guess>",
  "summary": "<3-4 sentence neutral summary>",
  "key_points": ["bullet1", "bullet2", "..."],
  "entities": ["entity1", "entity2"],
  "claims": [
    {{"text": "...", "confidence": "high/medium/low"}}
  ]
}}

Text:
\"\"\"{content}\"\"\"
"""

MAX_CONTENT_CHARS = 4000


def _build_prompt(text: str) -> str:
    """
    Clamp very long texts to avoid hitting model limits while keeping
    enough context for the summarizer to be useful.
    """
    truncated = text[:MAX_CONTENT_CHARS]
    if len(text) > MAX_CONTENT_CHARS:
        logger.debug(
            "LongFormSummarizerAgent truncating input from %s to %s characters",
            len(text),
            MAX_CONTENT_CHARS,
        )
    return SUMMARY_PROMPT.format(content=truncated)


def _build_collected_item(
    summary_payload: Dict[str, Any], source_name: str, source_url: str
) -> CollectedDataItem:
    """
    Converts the summary JSON into a CollectedDataItem so downstream
    agents can treat the summarizer output like any other evidence.
    """
    headline = summary_payload.get("headline") or "Summary"
    summary = summary_payload.get("summary") or ""
    key_points = summary_payload.get("key_points") or []
    entities = summary_payload.get("entities") or []

    lines = [
        f"Headline: {headline}",
        f"Summary: {summary}",
    ]
    if key_points:
        lines.append("Key points:")
        lines.extend(f"- {point}" for point in key_points)
    if entities:
        lines.append("Entities: " + ", ".join(entities))

    content = "\n".join(lines)

    return CollectedDataItem(
        content=content,
        relevance_score=0.75,
        meta=SourceMetaData(
            url=source_url,
            source_name=source_name,
            agent_name="LongFormSummarizerAgent",
        ),
    )


async def run(
    text: str,
    source_name: str,
    source_url: str,
    llm_client: Any,
) -> Dict[str, Optional[Any]]:
    """
    Summarizes long-form text into a structured JSON payload and
    returns both the parsed summary and a CollectedDataItem wrapper.
    """
    if not text or not text.strip():
        logger.info("LongFormSummarizerAgent received empty text; skipping.")
        return {}

    logger.info(SEPARATOR)
    logger.info("--- LONG FORM SUMMARIZER AGENT CALLED ---")
    logger.info("Summarizing source '%s' (%s)", source_name, source_url)

    prompt = _build_prompt(text)
    summary_payload = await llm_client.summarize_long_form(prompt)

    if not summary_payload:
        logger.warning("LongFormSummarizerAgent failed to obtain summary.")
        logger.info("--- LONG FORM SUMMARIZER AGENT FINISHED ---")
        logger.info(SEPARATOR)
        return {}

    collected_item = _build_collected_item(summary_payload, source_name, source_url)

    logger.info("LongFormSummarizerAgent summary complete.")
    logger.info("--- LONG FORM SUMMARIZER AGENT FINISHED ---")
    logger.info(SEPARATOR)

    return {
        "summary": summary_payload,
        "collected_item": collected_item,
    }


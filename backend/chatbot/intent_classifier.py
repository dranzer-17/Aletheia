import re
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
import sys

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from logger import get_logger
import importlib.util

# Import from misinformation-agent config
MISINFO_DIR = Path(__file__).resolve().parent.parent / "misinformation-agent"
misinfo_config_path = MISINFO_DIR / "config.py"
spec = importlib.util.spec_from_file_location("misinfo_config", misinfo_config_path)
if spec and spec.loader:
    misinfo_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(misinfo_config)
    GEMINI_API_KEY = misinfo_config.APP_CONFIG.get("GOOGLE_CLOUD_API_KEY", "")
    LLM_MODEL_NAME = misinfo_config.APP_CONFIG.get("LLM_MODEL_NAME", "gemini-2.0-flash-exp")
else:
    GEMINI_API_KEY = ""
    LLM_MODEL_NAME = "gemini-2.0-flash-exp"

# Import LLMClient from agentic_pipeline
MISINFO_DIR_STR = str(MISINFO_DIR)
if MISINFO_DIR_STR not in sys.path:
    sys.path.insert(0, MISINFO_DIR_STR)

from agentic_pipeline import LLMClient

logger = get_logger(__name__)

INTENT_PROMPT = """
Analyze the user's query and classify the intent. The user may:
1. Ask to verify/check a claim (misinformation detection)
2. Ask to detect AI-generated content (with media)
3. Ask to fetch/search for news
4. Have general conversation/questions
5. Combine multiple intents (hybrid)

Also detect any URLs in the query.

Return JSON ONLY with this format:
{{
  "intent": "misinformation_check" | "ai_detection" | "news_search" | "general_chat" | "hybrid",
  "confidence": 0.0-1.0,
  "detected_urls": ["url1", "url2"],
  "has_media": true/false,
  "requires_url_scraping": true/false,
  "reasoning": "brief explanation"
}}

Query: "{query}"
"""

class IntentClassifier:
    def __init__(self):
        self.llm_client = LLMClient(GEMINI_API_KEY, LLM_MODEL_NAME)
    
    def extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text using regex."""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        return urls
    
    async def classify(self, query: str, has_media: bool = False) -> Dict[str, Any]:
        """Classify user intent from query."""
        # First extract URLs
        detected_urls = self.extract_urls(query)
        
        # Build prompt
        prompt = INTENT_PROMPT.format(query=query)
        
        try:
            response = await self.llm_client.model.generate_content_async(prompt)
            text = response.text.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                # Fallback parsing
                result = json.loads(text)
            
            # Merge detected URLs
            if detected_urls:
                result["detected_urls"] = detected_urls
                if detected_urls:
                    result["requires_url_scraping"] = True
            
            # Override has_media if media is present
            if has_media:
                result["has_media"] = True
            
            logger.info(f"Intent classified: {result.get('intent')}, URLs: {len(detected_urls)}")
            return result
            
        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            # Fallback classification
            if detected_urls:
                return {
                    "intent": "misinformation_check",
                    "confidence": 0.7,
                    "detected_urls": detected_urls,
                    "has_media": has_media,
                    "requires_url_scraping": True,
                    "reasoning": "URLs detected, defaulting to misinformation check"
                }
            elif has_media:
                return {
                    "intent": "ai_detection",
                    "confidence": 0.7,
                    "detected_urls": [],
                    "has_media": True,
                    "requires_url_scraping": False,
                    "reasoning": "Media present, defaulting to AI detection"
                }
            else:
                return {
                    "intent": "general_chat",
                    "confidence": 0.5,
                    "detected_urls": [],
                    "has_media": False,
                    "requires_url_scraping": False,
                    "reasoning": "Fallback to general chat"
                }


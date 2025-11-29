import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import asyncio

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

MISINFO_DIR = BACKEND_ROOT / "misinformation-agent"
if str(MISINFO_DIR) not in sys.path:
    sys.path.insert(0, str(MISINFO_DIR))

from logger import get_logger
import importlib.util

# Import from misinformation-agent config (MISINFO_DIR already defined above)
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

# Import LLMClient and run_pipeline from agentic_pipeline
MISINFO_DIR_STR = str(MISINFO_DIR)
if MISINFO_DIR_STR not in sys.path:
    sys.path.insert(0, MISINFO_DIR_STR)

from agentic_pipeline import run_pipeline, LLMClient
from models.claim import Claim
from models.media import MediaItem

logger = get_logger(__name__)

class MisinformationTool:
    """Tool for misinformation detection pipeline."""
    
    def __init__(self):
        self.llm_client = LLMClient(GEMINI_API_KEY, LLM_MODEL_NAME)
        self.name = "misinformation_check"
        self.description = "Verifies claims and detects misinformation using multi-agent pipeline"
    
    async def execute(
        self,
        claim_text: str,
        use_web_search: bool = True,
        forced_agents: Optional[list] = None,
        media: Optional[List[Dict]] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """Execute misinformation detection pipeline."""
        try:
            # Convert media dicts to MediaItem objects
            media_items = []
            if media:
                for m in media:
                    # MediaItem expects: type, data_base64, mime_type, filename
                    # Convert bytes to base64 if needed
                    import base64
                    data_base64 = None
                    if isinstance(m.get("data"), bytes):
                        data_base64 = base64.b64encode(m.get("data")).decode('utf-8')
                    elif isinstance(m.get("data"), str):
                        data_base64 = m.get("data")
                    
                    media_items.append(MediaItem(
                        type="image" if m.get("type", "").startswith("image") else "document",
                        data_base64=data_base64,
                        mime_type=m.get("type", "application/octet-stream"),
                        filename=m.get("filename", "upload"),
                    ))
            
            # Run pipeline
            async def status_cb(stage: str):
                # Just log the stage for now
                logger.info(f"Pipeline stage: {stage}")
            
            final_state = await run_pipeline(
                claim_text=claim_text,
                use_web_search_override=use_web_search,
                forced_agents=forced_agents or [],
                status_callback=status_cb,
                verbose=False,
                exit_on_failure=False,
                media_items=media_items,
            )
            
            # Extract verdict and summary from final_state
            final_output = final_state.get("final_verification_output")
            if not final_output:
                raise Exception("Pipeline did not produce a verification output")
            
            verdict = final_output.verdict
            confidence = final_output.score.confidence
            summary = final_output.score.explanation
            
            # Extract sources
            sources = []
            if final_output.sources_used:
                for source in final_output.sources_used:
                    sources.append({
                        "title": source.source_name,
                        "url": source.url,
                        "snippet": "",
                        "relevance": 0.8,
                        "agent": "misinformation_pipeline",
                    })
            
            # Format response
            response_html = self._format_response(verdict, confidence, summary, sources)
            
            return {
                "success": True,
                "response": response_html,
                "sources": sources,
                "metadata": {
                    "verdict": verdict,
                    "confidence": confidence,
                    "tools_used": list(final_state.get("agents_used", [])),
                },
            }
            
        except Exception as e:
            logger.error(f"Misinformation tool error: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"<p>Error analyzing claim: {str(e)}</p>",
                "sources": [],
                "metadata": {},
            }
    
    def _format_response(self, verdict: str, confidence: float, summary: str, sources: List[Dict]) -> str:
        """Format response as natural, conversational HTML."""
        verdict_text = {
            "true": "verified as true",
            "false": "likely false or contains misinformation",
            "mixed": "mixed or unverified",
            "unknown": "unable to verify",
        }.get(verdict.lower(), "unable to verify")
        
        confidence_pct = confidence * 100
        
        # Create a natural, conversational response
        html = f"""
        <p>I understand your question. After analyzing your claim through our comprehensive misinformation detection pipeline, here's what I found:</p>
        
        <h3>Analysis Result</h3>
        <p>Based on the evidence gathered from multiple sources, the claim appears to be <strong>{verdict_text}</strong> with a confidence level of <strong>{confidence_pct:.1f}%</strong>.</p>
        
        <h3>Key Findings</h3>
        <p>{summary}</p>
        
        {f'<p><strong>Sources analyzed:</strong> {len(sources)} source{"s" if len(sources) != 1 else ""} were examined to reach this conclusion.</p>' if sources else ''}
        """
        return html.strip()


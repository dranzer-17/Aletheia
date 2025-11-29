import asyncio
import sys
from pathlib import Path
from typing import Optional

# Add misinformation_agent to path
MISINFO_DIR = Path(__file__).resolve().parent.parent / "misinformation_agent"
if str(MISINFO_DIR) not in sys.path:
    sys.path.append(str(MISINFO_DIR))

from agentic_pipeline import run_pipeline

async def analyze_text(text: str) -> str:
    """
    Analyze text for misinformation using the agent pipeline
    """
    try:
        # Run pipeline with verbose=False to avoid console output
        result = await run_pipeline(
            text, 
            use_web_search_override=True,
            verbose=False,
            exit_on_failure=False
        )
        
        # Extract and format the verification output
        final_output = result.get('final_verification_output')
        
        if not final_output:
            return "Could not produce a verification output."
        
        # Simplified format for WhatsApp (avoiding special characters that might cause issues)
        verdict_emoji = "✓" if final_output.verdict == "True" else "✗" if final_output.verdict == "False" else "?"
        
        response = f"""VERIFICATION COMPLETE

{verdict_emoji} Verdict: {final_output.verdict}
Score: {final_output.score.score:.1f}% (Confidence: {final_output.score.confidence:.2f})

Claim: {final_output.original_claim[:100]}...

Summary: {final_output.score.explanation[:200]}...
"""
        
        if final_output.true_news:
            response += f"\nFact: {final_output.true_news[:150]}..."
        
        return response.strip()
        
    except Exception as e:
        return f"Error analyzing text: {str(e)}"

async def analyze_image(image_bytes: bytes, context: Optional[str] = None) -> str:
    """
    Analyze image for misinformation
    Note: Current agent may not support images, so provide text context
    """
    if context:
        return await analyze_text(context)
    else:
        return "Image analysis not fully supported. Please provide text context."

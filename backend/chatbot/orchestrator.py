import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
import uuid
from datetime import datetime

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from logger import get_logger
from chatbot.intent_classifier import IntentClassifier
from chatbot.mcp_server import MCPServer
from chatbot.tools.url_scraper_tool import URLScraperTool

logger = get_logger(__name__)

class ChatOrchestrator:
    """Orchestrates chatbot conversations and tool execution."""
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.mcp_server = MCPServer()
        self.url_scraper = URLScraperTool()
    
    async def process_message(
        self,
        message: str,
        conversation_id: Optional[str],
        media: Optional[List[Dict]] = None,
        conversation_history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process user message and stream response."""
        # Store progress callback queue
        self._progress_queue = []
        """Process user message and stream response."""
        message_id = str(uuid.uuid4())
        
        # Classify intent
        has_media = media is not None and len(media) > 0
        yield {
            "type": "progress",
            "data": {"message": "Analyzing intent..."},
            "message_id": message_id,
        }
        
        intent_result = await self.intent_classifier.classify(message, has_media)
        intent = intent_result.get("intent", "general_chat")
        detected_urls = intent_result.get("detected_urls", [])
        
        yield {
            "type": "progress",
            "data": {"message": f"Intent: {intent.replace('_', ' ').title()}"},
            "message_id": message_id,
        }
        
        # Collect results
        all_sources = []
        all_responses = []
        tools_used = []
        metadata = {}
        
        # Handle URL scraping first if URLs detected
        scraped_content = ""
        if detected_urls:
            yield {
                "type": "progress",
                "data": {"message": f"Scraping {len(detected_urls)} URL(s)..."},
                "message_id": message_id,
            }
            
            url_result = await self.url_scraper.execute(detected_urls)
            if url_result.get("success"):
                all_sources.extend(url_result.get("sources", []))
                # Combine scraped content
                scraped_content = "\n\n".join([
                    f"**{item['title']}**\n{item['content']}"
                    for item in url_result.get("scraped_content", [])
                ])
                tools_used.append("url_scraper")
        
        # Handle hybrid intents sequentially
        if intent == "hybrid":
            # Determine sub-intents
            if has_media:
                # AI detection first, then misinformation
                intents_to_run = ["ai_detection", "misinformation_check"]
            else:
                intents_to_run = ["misinformation_check"]
        else:
            intents_to_run = [intent]
        
        # Execute tools sequentially
        for tool_intent in intents_to_run:
            try:
                if tool_intent == "misinformation_check":
                    # Combine original message with scraped content
                    claim_text = message
                    if scraped_content:
                        claim_text = f"{message}\n\nScraped content:\n{scraped_content}"
                    
                    yield {
                        "type": "progress",
                        "data": {"message": "Calling misinformation pipeline..."},
                        "message_id": message_id,
                    }
                    
                    result = await self.mcp_server.execute_tool(
                        "misinformation_check",
                        {
                            "claim_text": claim_text,
                            "use_web_search": True,
                            "media": media,
                        },
                        progress_callback=None,
                    )
                    
                    if result.get("success"):
                        all_responses.append(result.get("response", ""))
                        all_sources.extend(result.get("sources", []))
                        metadata.update(result.get("metadata", {}))
                        tools_used.append("misinformation_check")
                
                elif tool_intent == "ai_detection":
                    if not media:
                        continue
                    
                    # Process first media file
                    media_item = media[0]
                    file_bytes = media_item.get("data")  # Base64 decoded
                    file_type = "image" if media_item.get("type", "").startswith("image") else "video"
                    
                    yield {
                        "type": "progress",
                        "data": {"message": "Detecting AI content..."},
                        "message_id": message_id,
                    }
                    
                    result = await self.mcp_server.execute_tool(
                        "ai_detection",
                        {
                            "file_bytes": file_bytes,
                            "file_type": file_type,
                        },
                        progress_callback=lambda msg: self._send_progress(msg, message_id),
                    )
                    
                    if result.get("success"):
                        all_responses.append(result.get("response", ""))
                        metadata.update(result.get("metadata", {}))
                        tools_used.append("ai_detection")
                
                elif tool_intent == "news_search":
                    yield {
                        "type": "progress",
                        "data": {"message": "Searching for news..."},
                        "message_id": message_id,
                    }
                    
                    result = await self.mcp_server.execute_tool(
                        "news_search",
                        {
                            "query": message,
                            "max_results": 5,
                        },
                        progress_callback=lambda msg: self._send_progress(msg, message_id),
                    )
                    
                    if result.get("success"):
                        all_responses.append(result.get("response", ""))
                        all_sources.extend(result.get("sources", []))
                        metadata.update(result.get("metadata", {}))
                        tools_used.append("news_search")
                
                elif tool_intent == "general_chat":
                    message_lower = message.strip().lower()
                    summary_keywords = ("summarize", "summary", "recap")
                    question_keywords = ("what", "who", "when", "where", "why", "how", "which", "is", "are", "do", "does", "did", "can")
                    
                    is_summary_request = any(kw in message_lower for kw in summary_keywords)
                    is_question = message.strip().endswith("?") or any(
                        message_lower.startswith(f"{kw} ") for kw in question_keywords
                    )
                    
                    used_facts = False
                    if is_question and not is_summary_request:
                        yield {
                            "type": "progress",
                            "data": {"message": "Retrieving factual sources..."},
                            "message_id": message_id,
                        }
                        try:
                            facts_result = await self.mcp_server.execute_tool(
                                "facts_lookup",
                                {
                                    "query": message,
                                },
                                progress_callback=None,
                            )
                            if facts_result.get("success") and facts_result.get("response"):
                                all_responses.append(facts_result.get("response", ""))
                                all_sources.extend(facts_result.get("sources", []))
                                metadata.update({"facts_lookup": facts_result.get("metadata", {})})
                                tools_used.append("facts_lookup")
                                used_facts = True
                        except Exception as facts_error:
                            logger.error(f"Facts lookup tool error: {facts_error}")
                    
                    if used_facts:
                        continue
                    
                    yield {
                        "type": "progress",
                        "data": {"message": "Generating response..."},
                        "message_id": message_id,
                    }
                    
                    result = await self.mcp_server.execute_tool(
                        "general_chat",
                        {
                            "query": message,
                            "conversation_history": conversation_history,
                        },
                        progress_callback=None,
                    )
                    
                    if result.get("success"):
                        all_responses.append(result.get("response", ""))
                        tools_used.append("general_chat")
            
            except Exception as e:
                logger.error(f"Error executing tool {tool_intent}: {e}")
                # Continue with other tools
                continue
        
        # Combine responses into a natural, conversational format
        if all_responses:
            # If multiple responses, combine them naturally
            if len(all_responses) > 1:
                combined_response = f"""
                <p>I've analyzed your query and gathered information from multiple sources. Here's what I found:</p>
                <div class="space-y-4">
                {''.join([f'<div>{resp}</div>' for resp in all_responses])}
                </div>
                """
            else:
                combined_response = all_responses[0]
        else:
            combined_response = "<p>I apologize, but I wasn't able to generate a response to your query. Could you please rephrase it or provide more details?</p>"
        
        # Generate citations
        citations = list(range(len(all_sources))) if all_sources else []
        
        # Stream final response
        yield {
            "type": "content",
            "data": {
                "message": combined_response,
                "sources": all_sources,
                "citations": citations,
            },
            "message_id": message_id,
        }
        
        yield {
            "type": "complete",
            "data": {
                "intent": intent,
                "tools_used": tools_used,
                "metadata": metadata,
            },
            "message_id": message_id,
        }
    
    def _send_progress(self, message: str, message_id: str) -> None:
        """Helper to send progress updates (used in callbacks)."""
        # This will be handled by the streaming generator
        pass


import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from logger import get_logger
import importlib.util
from pathlib import Path

# Import from misinformation-agent config
MISINFO_DIR = Path(__file__).resolve().parent.parent.parent / "misinformation-agent"
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

from agentic_pipeline import LLMClient  # type: ignore

logger = get_logger(__name__)

class GeneralChatTool:
    """Tool for general conversation using Gemini."""
    
    def __init__(self):
        self.llm_client = LLMClient(GEMINI_API_KEY, LLM_MODEL_NAME)
        self.name = "general_chat"
        self.description = "General conversation and Q&A using Gemini"
    
    async def execute(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None,
        external_context: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """Execute general chat."""
        try:
            import re
            from html import unescape
            
            def extract_text_from_html(html_content: str) -> str:
                """Extract plain text from HTML content."""
                if not html_content:
                    return ""
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', '', html_content)
                # Decode HTML entities
                text = unescape(text)
                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text).strip()
                return text
            
            # Build context from history
            context_parts = []
            if conversation_history and len(conversation_history) > 0:
                # Include all messages, not just last 5, for better context
                for msg in conversation_history:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    
                    # Extract plain text from HTML if needed
                    if isinstance(content, str) and ('<' in content or '>' in content):
                        content = extract_text_from_html(content)
                    
                    # Format role name
                    role_name = "User" if role == "user" else "Assistant"
                    context_parts.append(f"{role_name}: {content}")
            
            history_section = "\n".join(context_parts) if context_parts else "No prior conversation history is available."
            external_section = external_context.strip() if external_context else "No supplemental external context is provided."
            
            prompt = f"""You are a helpful, factual AI assistant.

Conversation History:
{history_section}

External Context:
{external_section}

User Message: {query}

Instructions:
- If the conversation history does not contain the needed facts, rely on accurate world knowledge instead of saying it wasn't discussed.
- Clearly answer factual questions or provide summaries as requested.
- When you rely on external or general knowledge, respond confidently and concisely.

Assistant:"""
            
            # Generate response
            response = await self.llm_client.model.generate_content_async(prompt)
            response_text = response.text.strip()
            
            # Format as HTML (preserve markdown-like formatting)
            response_html = self._format_as_html(response_text)
            
            return {
                "success": True,
                "response": response_html,
                "sources": [],
                "metadata": {},
            }
            
        except Exception as e:
            logger.error(f"General chat tool error: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"<p>Error generating response: {str(e)}</p>",
                "sources": [],
                "metadata": {},
            }
    
    def _format_as_html(self, text: str) -> str:
        """Convert markdown-like text to HTML."""
        import re
        
        # Convert **bold** to <strong>
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        
        # Convert *italic* to <em>
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        
        # Convert # headings
        text = re.sub(r'^### (.+?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+?)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
        
        # Convert - lists to <ul>
        lines = text.split('\n')
        in_list = False
        html_lines = []
        
        for line in lines:
            if line.strip().startswith('- '):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                html_lines.append(f'<li>{line.strip()[2:]}</li>')
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                if line.strip():
                    html_lines.append(f'<p>{line}</p>')
        
        if in_list:
            html_lines.append('</ul>')
        
        return '\n'.join(html_lines) if html_lines else f'<p>{text}</p>'


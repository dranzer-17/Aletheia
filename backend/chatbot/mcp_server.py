from typing import Dict, List, Any
from chatbot.tools.misinformation_tool import MisinformationTool
from chatbot.tools.ai_detection_tool import AIDetectionTool
from chatbot.tools.news_search_tool import NewsSearchTool
from chatbot.tools.url_scraper_tool import URLScraperTool
from chatbot.tools.general_chat_tool import GeneralChatTool
from chatbot.tools.facts_tool import FactsLookupTool
from chatbot.schema import MCPTool, MCPGraph

class MCPServer:
    """Model Context Protocol Server for tool registry and execution."""
    
    def __init__(self):
        self.tools = {
            "misinformation_check": MisinformationTool(),
            "ai_detection": AIDetectionTool(),
            "news_search": NewsSearchTool(),
            "url_scraper": URLScraperTool(),
            "general_chat": GeneralChatTool(),
            "facts_lookup": FactsLookupTool(),
        }
        self.tool_registry = self._build_registry()
    
    def _build_registry(self) -> List[MCPTool]:
        """Build tool registry with metadata."""
        registry = []
        
        for name, tool in self.tools.items():
            registry.append(MCPTool(
                name=name,
                description=tool.description,
                parameters=self._get_parameters(name),
                return_type="Dict[str, Any]",
                agent=self._get_agent_name(name),
                endpoint=self._get_endpoint(name),
            ))
        
        return registry
    
    def _get_parameters(self, tool_name: str) -> Dict[str, Any]:
        """Get parameters for a tool."""
        params = {
            "misinformation_check": {
                "claim_text": "string",
                "use_web_search": "boolean",
                "forced_agents": "list",
                "media": "list",
            },
            "ai_detection": {
                "file_bytes": "bytes",
                "file_type": "string (image|video)",
            },
            "news_search": {
                "query": "string",
                "max_results": "integer",
            },
            "url_scraper": {
                "urls": "list[string]",
            },
            "general_chat": {
                "query": "string",
                "conversation_history": "list",
                "external_context": "string",
            },
            "facts_lookup": {
                "query": "string",
            },
        }
        return params.get(tool_name, {})
    
    def _get_agent_name(self, tool_name: str) -> str:
        """Get agent name for a tool."""
        agents = {
            "misinformation_check": "Misinformation Pipeline",
            "ai_detection": "Sightengine API",
            "news_search": "News Search Agent",
            "url_scraper": "URL Scraper Agent",
            "general_chat": "Gemini LLM",
            "facts_lookup": "Knowledge Lookup",
        }
        return agents.get(tool_name, "Unknown")
    
    def _get_endpoint(self, tool_name: str) -> str:
        """Get endpoint for a tool."""
        endpoints = {
            "misinformation_check": "/claims/analyze",
            "ai_detection": "/ai-detection/analyze-image or /analyze-video",
            "news_search": "Internal Agent",
            "url_scraper": "Internal Agent",
            "general_chat": "Gemini API",
            "facts_lookup": "Wikipedia + Google",
        }
        return endpoints.get(tool_name, "N/A")
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        progress_callback: Any = None,
    ) -> Dict[str, Any]:
        """Execute a tool by name."""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        tool = self.tools[tool_name]
        return await tool.execute(progress_callback=progress_callback, **parameters)
    
    def get_graph(self) -> MCPGraph:
        """Get graph representation of MCP tools and connections."""
        nodes = []
        edges = []
        
        # Add tool nodes
        for tool in self.tool_registry:
            nodes.append({
                "id": tool.name,
                "label": tool.name.replace("_", " ").title(),
                "type": "tool",
                "description": tool.description,
                "agent": tool.agent,
                "endpoint": tool.endpoint,
            })
        
        # Add agent nodes
        agents = set(tool.agent for tool in self.tool_registry)
        for agent in agents:
            nodes.append({
                "id": f"agent_{agent}",
                "label": agent,
                "type": "agent",
            })
        
        # Add edges (tools to agents)
        for tool in self.tool_registry:
            edges.append({
                "from": tool.name,
                "to": f"agent_{tool.agent}",
                "type": "uses",
            })
        
        # Add connections between tools
        connections = [
            ("url_scraper", "misinformation_check"),
            ("news_search", "url_scraper"),
            ("facts_lookup", "general_chat"),
        ]
        
        for from_tool, to_tool in connections:
            if from_tool in self.tools and to_tool in self.tools:
                edges.append({
                    "from": from_tool,
                    "to": to_tool,
                    "type": "feeds",
                })
        
        return MCPGraph(
            nodes=nodes,
            edges=edges,
            tools=self.tool_registry,
        )


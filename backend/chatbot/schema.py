from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    sources: Optional[List[Dict[str, Any]]] = None
    citations: Optional[List[int]] = None
    intent: Optional[str] = None
    tools_used: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    media: Optional[List[Dict[str, Any]]] = None  # For voice/image attachments

class ChatResponse(BaseModel):
    message: str  # HTML formatted
    sources: List[Dict[str, Any]]
    citations: List[int]
    intent: str
    tools_used: List[str]
    metadata: Dict[str, Any]
    conversation_id: str
    message_id: str

class StreamingChunk(BaseModel):
    type: str  # "progress", "content", "sources", "complete"
    data: Dict[str, Any]
    message_id: str

class MCPTool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    return_type: str
    agent: Optional[str] = None
    endpoint: Optional[str] = None

class MCPGraph(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    tools: List[MCPTool]


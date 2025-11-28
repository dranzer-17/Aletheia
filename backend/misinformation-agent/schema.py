from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl

from models.media import MediaItem

class ScoreSchema(BaseModel):
    score: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    explanation: str


class SourceSchema(BaseModel):
    url: HttpUrl | str
    source_name: str
    agent_name: Optional[str] = None
    timestamp: Optional[datetime] = None


class ClaimAnalyzeRequest(BaseModel):
    claim_text: str = Field(
        "",
        min_length=0,
        max_length=1_000,
        description="Textual claim provided by the user (optional when media is supplied).",
    )
    use_web_search: bool = True
    forced_agents: List[str] = Field(default_factory=list)
    media: List[MediaItem] = Field(
        default_factory=list,
        description="Optional media attachments (images, documents, URLs).",
    )


class ClaimAnalyzeResponse(BaseModel):
    claimId: str
    status: str


class ClaimVerdictDBSchema(BaseModel):
    claimId: str
    userId: Union[str, int]
    claim_text: str
    status: str = "processing"
    processing_stage: Optional[str] = None
    verdict: Optional[str] = None
    confidence: Optional[float] = None
    score: Optional[ScoreSchema] = None
    true_news: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    sources_used: List[SourceSchema] = Field(default_factory=list)
    sentiment_analysis: Optional[Dict[str, Any]] = None
    emotion_analysis: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[Dict[str, Any]] = None


class ClaimAgentRecord(BaseModel):
    claimId: str
    agent_key: str
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    relevance_score: Optional[float] = None
    output: Any
    created_at: datetime = Field(default_factory=datetime.utcnow)


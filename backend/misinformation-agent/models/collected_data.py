from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class SourceMetaData(BaseModel):
    """
    Metadata about the source from which information was collected.
    """
    url: str = Field(..., description="The URL of the source.")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the data was collected.")
    source_name: str = Field(..., description="A human-readable name for the source (e.g., 'Times of India', 'News API').")
    agent_name: str = Field(..., description="The name of the agent that collected this data.")

class CollectedDataItem(BaseModel):
    """
    Represents a single piece of collected information from a source.
    """
    content: str = Field(..., description="The textual content collected from the source.")
    relevance_score: Optional[float] = Field(None, ge=0, le=1, description="A score indicating relevance to the original claim (0-1).")
    meta: SourceMetaData = Field(..., description="Metadata about the source of this item.")

class CollectedDataBundle(BaseModel):
    """
    A collection of all information gathered from various data collection agents.
    """
    data: List[CollectedDataItem] = Field(default_factory=list, description="List of collected data items.")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered during data collection.")
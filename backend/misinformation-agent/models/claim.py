from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID, uuid4

class Claim(BaseModel):
    """
    Represents the initial claim or piece of information to be verified.
    """
    text: str = Field(..., description="The actual text content of the claim.")
    claim_id: UUID = Field(default_factory=uuid4, description="Unique identifier for the claim.")
    context: Optional[str] = Field(None, description="Any surrounding text or URL where the claim was found.")
    keywords: Optional[List[str]] = Field(None, description="Extracted keywords from the claim, useful for agent routing.")
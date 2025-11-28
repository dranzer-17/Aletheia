from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from .collected_data import SourceMetaData # Import SourceMetaData from the same models package

class VerificationScore(BaseModel):
    """
    Represents the numerical score and confidence for a claim's veracity.
    """
    score: float = Field(..., ge=0, le=1, description="A numerical score (0-1) representing the veracity of the claim, where 1 is completely true and 0 is completely false.")
    confidence: float = Field(..., ge=0, le=1, description="A confidence level (0-1) for the given score.")
    explanation: str = Field(..., description="A detailed explanation for the score and verdict.")

class VerificationOutput(BaseModel):
    """
    The final output of the misinformation detection and verification process.
    """
    claim_id: UUID = Field(..., description="The unique ID of the original claim.")
    original_claim: str = Field(..., description="The original text of the claim that was verified.")
    verdict: str = Field(..., description="The final verdict ('True', 'False', 'Partially True', 'Unverified').")
    score: VerificationScore = Field(..., description="The detailed score, confidence, and explanation.")
    true_news: Optional[str] = Field(None, description="Corrected or factual information if the original claim was false or partially true.")
    sources_used: List[SourceMetaData] = Field(default_factory=list, description="List of meta-data for all sources actually used in the verification process.")
    errors: List[str] = Field(default_factory=list, description="Any high-level errors encountered during the verification process.")
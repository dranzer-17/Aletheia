from pydantic import BaseModel
from typing import Optional

class WhatsAppMessage(BaseModel):
    body: Optional[str] = None
    media_url: Optional[str] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None

class DetectionRequest(BaseModel):
    text: Optional[str] = None
    image_url: Optional[str] = None

class DetectionResponse(BaseModel):
    result: str

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class MediaItem(BaseModel):
    """
    Represents any media attachment provided for claim verification.
    Currently optimized for images but extensible to documents or URLs.
    """

    type: Literal["image", "document", "url"] = Field(
        ..., description="Type of media attachment."
    )
    url: Optional[HttpUrl | str] = Field(
        default=None, description="Remote URL for the media asset if available."
    )
    data_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded payload for the media (used for direct uploads).",
    )
    mime_type: Optional[str] = Field(
        default=None, description="MIME type of the attachment (e.g., image/png)."
    )
    filename: Optional[str] = Field(
        default=None, description="Original filename if provided by the client."
    )
    description: Optional[str] = Field(
        default=None, description="Optional user supplied context for the media."
    )



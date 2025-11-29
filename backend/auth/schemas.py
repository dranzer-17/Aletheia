from pydantic import BaseModel, EmailStr, Field, BeforeValidator
from typing import Optional, Annotated

# Helper to convert MongoDB _id to string
PyObjectId = Annotated[str, BeforeValidator(str)]

# Base Schema (Shared properties)
class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None  # <--- THIS IS CRITICAL. It must be here.

# Schema for Signup (Frontend sends this)
class UserCreate(UserBase):
    password: str
    # full_name is inherited from UserBase, so it is accepted here automatically.

# Schema for Reading Data (What we send back to Frontend)
class UserResponse(UserBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: Optional[int] = Field(default=None, alias="user_id")
    
    class Config:
        populate_by_name = True

# Schema for JWT Token
class Token(BaseModel):
    access_token: str
    token_type: str
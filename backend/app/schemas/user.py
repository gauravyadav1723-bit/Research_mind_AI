from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from beanie import PydanticObjectId

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters.")

class UserOut(BaseModel):
    id: PydanticObjectId
    email: EmailStr
    is_active: bool
    created_at: datetime

    class Config:
        populate_by_name = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None

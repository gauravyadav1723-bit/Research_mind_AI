from datetime import datetime
from typing import Optional, Dict, Any
from beanie import Document, Indexed
from pydantic import Field
from beanie import PydanticObjectId

class DocumentChunk(Document):
    document_id: Indexed(PydanticObjectId)
    text: str
    page: int
    section: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "chunks"

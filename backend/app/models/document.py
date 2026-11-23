from datetime import datetime
from beanie import Document, Indexed
from pydantic import Field
from beanie import PydanticObjectId

class ResearchDocument(Document):
    filename: Indexed(str)
    file_path: str
    file_size: int
    project_id: Indexed(PydanticObjectId)
    user_id: Indexed(PydanticObjectId)
    status: str = "uploaded"  # uploaded, processing, indexed, failed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "documents"

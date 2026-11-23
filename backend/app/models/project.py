from datetime import datetime
from typing import Optional, List
from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field

class ResearchProject(Document):
    title: Indexed(str)
    description: Optional[str] = None
    user_id: Optional[PydanticObjectId] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)


    class Settings:
        name = "projects"

    async def update_project(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        await self.save()

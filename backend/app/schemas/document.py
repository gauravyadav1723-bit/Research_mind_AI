from datetime import datetime
from pydantic import BaseModel
from beanie import PydanticObjectId

class DocumentOut(BaseModel):
    id: PydanticObjectId
    filename: str
    file_size: int
    project_id: PydanticObjectId
    user_id: PydanticObjectId
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True

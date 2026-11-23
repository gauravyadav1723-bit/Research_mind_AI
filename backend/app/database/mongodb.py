from pymongo import AsyncMongoClient
from beanie import init_beanie
from app.config.settings import settings
from app.models.project import ResearchProject
from app.models.user import User
from app.models.document import ResearchDocument
from app.models.chunk import DocumentChunk

async def init_db():
    # Create Async MongoClient
    client = AsyncMongoClient(settings.MONGODB_URL)
    
    # Initialize Beanie with document models
    await init_beanie(
        database=client[settings.MONGODB_DB_NAME],
        document_models=[
            ResearchProject,
            User,
            ResearchDocument,
            DocumentChunk,
        ]
    )





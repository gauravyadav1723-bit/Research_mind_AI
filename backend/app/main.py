import contextlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config.settings import settings
from app.database.mongodb import init_db
from app.api.projects import router as projects_router
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MongoDB and Beanie on startup
    await init_db()
    yield

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API powering the ResearchMind-AI application.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin).strip("/") for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(projects_router, prefix=f"{settings.API_V1_STR}/projects", tags=["projects"])
app.include_router(documents_router, prefix=f"{settings.API_V1_STR}/documents", tags=["documents"])



@app.get("/")
def read_root():
    return {"message": "Welcome to ResearchMind-AI API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}


from typing import List, Optional
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, description="The research question to ask.")
    top_k: int = Field(default=4, ge=1, le=10, description="Number of context chunks to retrieve.")

class SourceCitation(BaseModel):
    page: int
    section: str
    snippet: str
    author: str
    year: int

class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
